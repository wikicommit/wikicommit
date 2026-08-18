#!/usr/bin/env python3
"""Validate wiki page frontmatter against schema specifications.

Usage:
    python .wikicommit/scripts/validate_frontmatter.py               # all files
    python .wikicommit/scripts/validate_frontmatter.py <path>...     # specific files

Exit code: 0 = no errors (warnings OK), 1 = at least one ERROR.
"""

import functools
import os
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _schemaorg_vocab import ancestors, load_or_build_index, property_in_domain
from _wikilink import ENTITY_DIR, resolve_stored_entity_path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LANG_RE = re.compile(r"^[a-z]{2}$")
COMMIT_HASH_RE = re.compile(r"^[0-9a-f]{40}$")

VALID_REVIEW_STATUSES = {"pending", "reviewed"}
VALID_REMOVED_REASONS = {"obsolete", "merged", "gdpr"}
VALID_SOURCE_TYPES = {"path", "url", "wikicommit", "manual"}

# Top-level fields with a defined structural/bookkeeping/common-identifier
# role in the frontmatter split (docs/DesignDoc-data.md §4.1, Issue #495).
# Never treated as a possible misplaced Schema.org property by
# validate_schema_properties()'s flat-field scan below.
COMMON_TOP_LEVEL_FIELDS = {
    "title", "lang", "type", "sources", "tags", "review_status", "expires_at",
    "generated_at", "generated_by", "wikidata", "sameAs", "aliases", "properties",
    "translated_from", "source_commit", "translated_at", "translated_by",
    "derived_from", "status", "removed_at", "removed_reason", "merged_into",
}


@functools.lru_cache(maxsize=None)
def _load_schema_file(schema_path: Path) -> tuple[dict, str]:
    fm, err = parse_frontmatter(schema_path)
    return (fm or {}), (err if err else "")


def resolve_type_schema(type_value: str, schema_dir: Path) -> tuple[dict, str]:
    """Return (type_schema_dict, fallback_warning).

    If the schema file for the type does not exist, returns ({}, warning).
    The default.md required fields are applied separately, so we return {}
    instead of re-loading default.md to avoid double-counting.

    This is a *local-file-existence* check only — it says nothing about
    whether the type is real. A typo'd `type:` with a matching (however it
    got there) `.wikicommit/schema/<name>.md` on disk produces no warning
    here at all. validate_schema_properties() below runs an independent,
    *Schema.org-vocabulary-existence* check for the same `type:` value
    (Issue #512) specifically to catch that gap — the two checks can
    legitimately disagree (e.g. fire together: no local file *and* not in
    the vocabulary, for the common case of a plain typo with nothing built
    for it yet) since they're checking different things.
    """
    if not type_value.startswith("schema:"):
        return {}, ""

    type_name = type_value[len("schema:"):]  # e.g. "Person" or "custom/Decision"
    schema_path = schema_dir / f"{type_name}.md"

    if schema_path.exists():
        return _load_schema_file(schema_path)

    return {}, (
        f"スキーマファイルが見つかりません: .wikicommit/schema/{type_name}.md"
        "、default.md にフォールバックします"
    )


def build_required_fields(default_schema: dict, type_schema: dict) -> list[str]:
    default_req = default_schema.get("wikicommit", {}).get("frontmatter", {}).get("required") or []
    type_req = type_schema.get("wikicommit", {}).get("frontmatter", {}).get("required") or []
    seen: set[str] = set()
    result = []
    for f in list(default_req) + list(type_req):
        if f not in seen:
            seen.add(f)
            result.append(f)
    return result


def validate_source_item(src: object, idx: int, repo_root: Path) -> list[tuple[str, str]]:
    errors: list[tuple[str, str]] = []
    if not isinstance(src, dict):
        return [(f"sources[{idx}]", "dict 型でなければなりません")]

    src_type = src.get("type")
    if src_type is None:
        return [(f"sources[{idx}].type", "必須フィールドがありません")]
    if src_type not in VALID_SOURCE_TYPES:
        return [(f"sources[{idx}].type", f"無効な種別です: {src_type!r}")]

    if src_type == "path":
        if "path" not in src:
            errors.append((f"sources[{idx}].path", "必須フィールドがありません"))
        else:
            if not (repo_root / str(src["path"])).exists():
                errors.append((f"sources[{idx}].path", f"ファイルが存在しません: {src['path']}"))
        if "hash" not in src:
            errors.append((f"sources[{idx}].hash", "必須フィールドがありません"))
        elif not str(src["hash"]).startswith("sha256:"):
            errors.append((f"sources[{idx}].hash", "`sha256:` プレフィックスがありません"))

    elif src_type in ("url", "wikicommit"):
        if "url" not in src:
            errors.append((f"sources[{idx}].url", "必須フィールドがありません"))
        elif not str(src["url"]).startswith("https://"):
            errors.append((f"sources[{idx}].url", "`https://` で始まっていません"))
        if "hash" not in src:
            errors.append((f"sources[{idx}].hash", "必須フィールドがありません"))
        elif not str(src["hash"]).startswith("sha256:"):
            errors.append((f"sources[{idx}].hash", "`sha256:` プレフィックスがありません"))

    elif src_type == "manual":
        if "author" not in src:
            errors.append((f"sources[{idx}].author", "必須フィールドがありません"))
        elif not str(src["author"]).strip():
            errors.append((f"sources[{idx}].author", "空文字列は使用できません"))
        if "created_at" not in src:
            errors.append((f"sources[{idx}].created_at", "必須フィールドがありません"))
        elif not DATE_RE.match(str(src["created_at"])):
            errors.append((f"sources[{idx}].created_at", "`YYYY-MM-DD` 形式でなければなりません"))

    return errors


@functools.lru_cache(maxsize=None)
def _cached_vocab_index() -> tuple[dict | None, str]:
    """Load .wikicommit/schemaorg-vocab.json (or build it) once per script
    run, regardless of how many pages have Schema.org properties to check —
    same one-shot-per-run intent as default_schema in main(), just lazy
    (only triggered once the first such page is validated) so a run with no
    typed pages never touches the vocabulary at all. Thin memoizing wrapper
    around load_or_build_index() — see validate_schema_properties() for how
    a (None, error) result is surfaced.

    The failure branch is cached too (not just success): a persistent
    failure (e.g. genuinely offline, no committed cache) would otherwise
    retry the ~30s network fetch for every single remaining page in the run.
    A transient blip on the very first page degrading the rest of that one
    run to warnings is the accepted trade-off for bounding worst-case
    runtime to a single fetch attempt."""
    return load_or_build_index()


def validate_schema_properties(fm: dict, type_value: object) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """The machine-checkable half of the frontmatter split introduced by
    Issue #495 (`properties:` nests Schema.org-vocabulary-backed fields;
    everything else — structural fields, WikiCommit bookkeeping, common
    cross-type identifiers — stays flat at the top level,
    docs/DesignDoc-data.md §4.1). Three checks, all keyed off the same
    type/vocabulary resolution so a page pays for it at most once:

    1. `type:` itself resolves to a real Schema.org type (Issue #512) — a
       non-`custom/` type absent from the vocabulary is reported as an ERROR
       and short-circuits checks 2–3 below (there's no ancestry chain to
       walk for a type that doesn't exist, so neither can be evaluated).
    2. Every key under `properties:` (if present) actually belongs to the
       page's `type:` (or an ancestor type) per Schema.org's domainIncludes.
       Mirrors check_schema_org_type.py's --property verification, sharing
       its domain-membership logic via _schemaorg_vocab.py's
       property_in_domain().
    3. No top-level frontmatter key (outside COMMON_TOP_LEVEL_FIELDS) is
       itself a Schema.org property that belongs to this type — catching a
       property left flat instead of nested under `properties:` (e.g. an
       LLM or hand-edit reverting to the pre-Issue-#495 shape), which
       otherwise passes silently: nothing else in this file inspects
       "extra" top-level keys it doesn't recognize.

    Custom types (`schema:custom/...`) have no corresponding Schema.org
    vocabulary entry — their properties are documented in prose in the
    schema file itself instead (docs/DesignDoc-data.md §5.3) and reviewed by
    a human via wikicommit-schema-propose, not machine-verified here.

    Returns (errors, warnings), following validate_file()'s own convention
    so a caller just extends both lists — unlike every other check in this
    file, a lookup failure here (vocabulary unavailable) is reported as a
    WARNING rather than silently skipped or escalated to an ERROR: it's a
    real, visible degradation of this specific check, but not reason enough
    to block the quality gate over a network hiccup or a deleted-but-not-
    yet-rebuilt schemaorg-vocab.json (docs/DesignDoc-ScriptSpec.md).
    """
    errors: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []

    # `properties:` absent, or present with nothing under it (YAML null) —
    # both mean "no type-specific properties on this page," not an error.
    properties = fm.get("properties")
    if properties is not None and not isinstance(properties, dict):
        errors.append(("properties", "dict 型でなければなりません"))
        properties = None

    if not type_value or not str(type_value).startswith("schema:"):
        return errors, warnings  # `type` itself is already reported as an error elsewhere

    type_name = str(type_value)[len("schema:"):]
    if type_name.startswith("custom/"):
        return errors, warnings

    index, err = _cached_vocab_index()
    if index is None:
        if properties:
            warnings.append(("properties", f"Schema.org 語彙を取得できなかったため検証をスキップしました: {err}"))
        return errors, warnings

    types, props = index["types"], index["properties"]
    if type_name not in types:
        # A non-custom `type:` with no Schema.org vocabulary entry is a typo
        # or a non-standard-naming ad-hoc type, not a legitimate installed
        # type resolve_type_schema() just hasn't seen a local schema file
        # for yet (Issue #512) — that local-file case is resolve_type_schema()'s
        # own, separate WARNING. Without this check, a typo'd/non-existent
        # type that happens to have *some* `.wikicommit/schema/<name>.md`
        # file on disk (however it got there) passes silently, with its
        # `properties:` never machine-verified against anything.
        errors.append(("type", f"schema:{type_name} は Schema.org 語彙に存在しません"))
        return errors, warnings

    ancestry = ancestors(type_name, types)

    if properties:
        for key in properties:
            in_domain = property_in_domain(str(key), ancestry, props)
            if in_domain is None:
                errors.append((f"properties.{key}", "Schema.org 語彙に存在しません"))
            elif not in_domain:
                errors.append((f"properties.{key}", f"schema:{type_name} およびその祖先型のいずれにも属しません"))

    for key in fm:
        if key in COMMON_TOP_LEVEL_FIELDS:
            continue
        if property_in_domain(str(key), ancestry, props):
            errors.append((
                key,
                f"schema:{type_name} の Schema.org プロパティです。properties: 配下にネストしてください"
                "（トップレベルへの平置きは不可。Issue #495）",
            ))

    return errors, warnings


def validate_file(
    path: Path,
    repo_root: Path,
    default_schema: dict,
    schema_dir: Path,
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Return (errors, warnings) for one wiki page file."""
    errors: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []

    fm, parse_error = parse_frontmatter(path)
    if fm is None:
        return [("frontmatter", parse_error)], []

    is_translation = "translated_from" in fm
    is_derived = "derived_from" in fm
    is_index = path.name == "index.md"
    exempt_sources = is_translation or is_derived or is_index

    # Resolve type schema
    type_value = fm.get("type")
    type_schema: dict = {}
    if type_value is not None:
        if not str(type_value).startswith("schema:"):
            errors.append(("type", "`schema:` プレフィックスで始まっていません"))
        else:
            type_schema, fallback_warn = resolve_type_schema(str(type_value), schema_dir)
            if fallback_warn:
                warnings.append(("type", fallback_warn))

    # Required fields check
    for field in build_required_fields(default_schema, type_schema):
        if field == "sources" and exempt_sources:
            continue
        if field not in fm:
            errors.append((field, "必須フィールドがありません"))

    # --- Format validation (only when field is present) ---

    if "title" in fm and not str(fm["title"]).strip():
        errors.append(("title", "空文字列は使用できません"))

    if "lang" in fm and not LANG_RE.match(str(fm["lang"])):
        errors.append(("lang", "ISO 639-1 の 2 文字小文字コードでなければなりません"))

    if "sources" in fm:
        sources = fm["sources"]
        if not isinstance(sources, list):
            errors.append(("sources", "list 型でなければなりません"))
        else:
            if not exempt_sources and len(sources) == 0:
                errors.append(("sources", "1 件以上のソースが必要です"))
            for i, src in enumerate(sources):
                errors.extend(validate_source_item(src, i, repo_root))

    if "review_status" in fm:
        if fm["review_status"] not in VALID_REVIEW_STATUSES:
            errors.append(
                ("review_status", "`pending` / `reviewed` のいずれかでなければなりません")
            )
    elif type_value:
        warnings.append(("review_status", "未設定（pending として扱います）"))

    if "expires_at" in fm and not DATE_RE.match(str(fm["expires_at"])):
        errors.append(("expires_at", "`YYYY-MM-DD` 形式でなければなりません"))

    if "wikidata" in fm and not str(fm["wikidata"]).startswith("wd:Q"):
        errors.append(("wikidata", "`wd:Q` で始まっていません"))

    if "tags" in fm:
        tags = fm["tags"]
        if not isinstance(tags, list):
            errors.append(("tags", "list 型でなければなりません"))
        else:
            for i, tag in enumerate(tags):
                if not isinstance(tag, str):
                    errors.append((f"tags[{i}]", "string 型でなければなりません"))

    if "generated_at" in fm and not DATE_RE.match(str(fm["generated_at"])):
        errors.append(("generated_at", "`YYYY-MM-DD` 形式でなければなりません"))

    if "generated_by" in fm and not str(fm["generated_by"]).strip():
        errors.append(("generated_by", "空文字列は使用できません"))

    prop_errors, prop_warnings = validate_schema_properties(fm, type_value)
    errors.extend(prop_errors)
    warnings.extend(prop_warnings)

    # Translation page fields
    if is_translation:
        translated_from = fm.get("translated_from")
        if not translated_from or not str(translated_from).strip():
            errors.append(("translated_from", "空文字列は使用できません"))
        else:
            tf_path = resolve_stored_entity_path(str(translated_from), repo_root)
            if not tf_path.exists():
                errors.append(("translated_from", f"ファイルが存在しません: {translated_from}"))

        source_commit = fm.get("source_commit")
        if source_commit is None:
            errors.append(("source_commit", "必須フィールドがありません"))
        elif str(source_commit) != "" and not COMMIT_HASH_RE.match(str(source_commit)):
            # Empty string is allowed: wikicommit-translate writes it when the source
            # page has no commits yet (not yet merged). check_translation_status.py
            # already treats this as STALE by design (Issue #409).
            errors.append(
                ("source_commit", "40 文字の git コミットハッシュ（小文字 16 進数）、または空文字列（原文未コミット時）でなければなりません")
            )

        if "translated_at" in fm and not DATE_RE.match(str(fm["translated_at"])):
            errors.append(("translated_at", "`YYYY-MM-DD` 形式でなければなりません"))

        if "translated_by" in fm and not str(fm["translated_by"]).strip():
            errors.append(("translated_by", "空文字列は使用できません"))

    # Synthesized page fields (wikicommit-synthesize output; derived_from is the
    # multi-source analog of translated_from/source_commit)
    if is_derived:
        derived_from = fm.get("derived_from")
        if not isinstance(derived_from, list):
            errors.append(("derived_from", "list 型でなければなりません"))
        elif len(derived_from) == 0:
            errors.append(("derived_from", "1 件以上の要素が必要です"))
        else:
            for i, entry in enumerate(derived_from):
                if not isinstance(entry, dict):
                    errors.append((f"derived_from[{i}]", "dict 型でなければなりません"))
                    continue

                entry_path = entry.get("path")
                if not entry_path or not str(entry_path).strip():
                    errors.append((f"derived_from[{i}].path", "必須フィールドがありません"))
                elif not resolve_stored_entity_path(str(entry_path), repo_root).exists():
                    errors.append((f"derived_from[{i}].path", f"ファイルが存在しません: {entry_path}"))

                entry_commit = entry.get("source_commit")
                if entry_commit is None:
                    errors.append((f"derived_from[{i}].source_commit", "必須フィールドがありません"))
                elif str(entry_commit) != "" and not COMMIT_HASH_RE.match(str(entry_commit)):
                    # Empty string is allowed: wikicommit-synthesize writes it when a
                    # grounding page has no commits yet, same convention as
                    # translated_from/source_commit above (Issue #409).
                    # check_derivation_freshness.py already treats this as STALE.
                    errors.append(
                        (
                            f"derived_from[{i}].source_commit",
                            "40 文字の git コミットハッシュ（小文字 16 進数）、または空文字列（原文未コミット時）でなければなりません",
                        )
                    )

    # Removed page fields
    status = fm.get("status")
    if status is not None:
        if status != "removed":
            errors.append(("status", "`removed` のみ使用できます"))
        else:
            if "removed_at" not in fm:
                errors.append(("removed_at", "必須フィールドがありません"))
            elif not DATE_RE.match(str(fm["removed_at"])):
                errors.append(("removed_at", "`YYYY-MM-DD` 形式でなければなりません"))

            removed_reason = fm.get("removed_reason")
            if removed_reason is not None:
                if removed_reason not in VALID_REMOVED_REASONS:
                    errors.append(
                        ("removed_reason", "`obsolete` / `merged` / `gdpr` のいずれかでなければなりません")
                    )
                if removed_reason == "merged":
                    merged_into = fm.get("merged_into")
                    if merged_into is None:
                        errors.append(("merged_into", "`removed_reason: merged` の場合は必須です"))
                    else:
                        mi_path = repo_root / str(merged_into)
                        if not mi_path.exists():
                            errors.append(("merged_into", f"ファイルが存在しません: {merged_into}"))

    return errors, warnings


def emit_github_annotation(level: str, file_str: str, message: str) -> None:
    print(f"::{level} file={file_str},title=frontmatter::{message}")


def main() -> int:
    repo_root = Path.cwd()
    schema_dir = repo_root / ".wikicommit" / "schema"
    entity_dir = repo_root / ENTITY_DIR
    is_gha = os.environ.get("GITHUB_ACTIONS") == "true"

    # Collect target files
    if len(sys.argv) > 1:
        target_files: list[Path] = [Path(a) for a in sys.argv[1:]]
    else:
        if not entity_dir.exists():
            print("OK: 0 files validated, 0 errors, 0 warnings")
            return 0
        target_files = sorted(entity_dir.rglob("*.md"))

    if not target_files:
        print("OK: 0 files validated, 0 errors, 0 warnings")
        return 0

    default_schema, default_err = parse_frontmatter(schema_dir / "default.md")
    if default_err:
        print(f"ERROR: default.md の frontmatter を読み込めませんでした: {default_err}", file=sys.stderr)
        return 1
    default_schema = default_schema or {}

    total_errors = 0
    total_warnings = 0

    for fp in target_files:
        fp = Path(fp)
        if not fp.exists():
            msg = "ファイルが存在しません"
            print(f"ERROR: {fp}: {msg}", file=sys.stderr)
            total_errors += 1
            continue

        try:
            rel = fp.relative_to(repo_root)
        except ValueError:
            rel = fp

        rel_str = str(rel)

        errors, warnings = validate_file(fp, repo_root, default_schema, schema_dir)

        for field, msg in errors:
            print(f"ERROR: {rel_str}: {field}: {msg}")
            if is_gha:
                emit_github_annotation("error", rel_str, f"{field}: {msg}")
            total_errors += 1

        for field, msg in warnings:
            print(f"WARNING: {rel_str}: {field}: {msg}")
            if is_gha:
                emit_github_annotation("warning", rel_str, f"{field}: {msg}")
            total_warnings += 1

    print(
        f"OK: {len(target_files)} files validated,"
        f" {total_errors} errors, {total_warnings} warnings"
    )
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
