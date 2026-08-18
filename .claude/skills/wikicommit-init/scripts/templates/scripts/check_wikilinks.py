#!/usr/bin/env python3
"""Check WikiLinks in wiki pages for broken or removed references.

Usage:
    python .wikicommit/scripts/check_wikilinks.py --changed <path>... [--deleted <path>...]

Exit code: 0 = no ERROR (WARNINGs OK), 1 = at least one ERROR.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter_cached
from _wikilink import ENTITY_DIR, WIKILINK_RE, parse_wiki_path

IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def _emit_annotation(level: str, title: str, message: str, file_path: str | None = None) -> None:
    if IN_GITHUB_ACTIONS:
        loc = f"file={file_path}," if file_path else ""
        print(f"::{level} {loc}title={title}::{message}")


def load_primary_lang(repo_root: Path) -> str:
    # Fallback is "en" to match init.py's --primary-lang default (Issue #159 changed the
    # tool-wide default from "ja"; Issue #376 brought this fallback in line with it). Only
    # reached for a config.yml missing/malformed enough to lack an explicit primary_lang —
    # every config.yml init.py generates always has one.
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return "en"
        translation = data.get("translation") or {}
        return str(translation.get("primary_lang", "en") or "en")
    except Exception:
        return "en"


def load_frontmatter(path: Path) -> dict:
    fm, err = parse_frontmatter_cached(path)
    if err:
        print(f"WARNING: {path}: {err}")
        return {}
    return fm


def get_lang(path: Path, primary_lang: str) -> str:
    fm = load_frontmatter(path)
    return str(fm.get("lang", primary_lang))


def is_removed(path: Path) -> bool:
    fm = load_frontmatter(path)
    return fm.get("status") == "removed"


def extract_wikilinks(path: Path) -> list[tuple[str, str]]:
    """Return list of (Type, slug) tuples from [[Type/slug]] in file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [(m.group(1), m.group(2)) for m in WIKILINK_RE.finditer(content)]


def type_slug_from_wiki_path(path: Path, entity_dir: Path) -> tuple[str, str] | None:
    """Derive (Type, slug) from a page path under entity_dir.

    Type may contain "/" for nested custom types (e.g. custom/Decision).
    """
    resolved = parse_wiki_path(path, entity_dir)
    if resolved is None:
        return None
    _, type_name, slug = resolved
    return type_name, slug


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check WikiLinks in wiki pages for broken or removed references."
    )
    parser.add_argument("--changed", nargs="+", default=[], metavar="PATH",
                        help="Files being added or modified (required)")
    parser.add_argument("--deleted", nargs="+", default=[], metavar="PATH",
                        help="Files being marked as status: removed (optional)")
    args = parser.parse_args()

    if not args.changed and not args.deleted:
        print("OK: 0 files checked, 0 errors, 0 warnings")
        return 0

    repo_root = Path.cwd()
    entity_dir = repo_root / ENTITY_DIR
    primary_lang = load_primary_lang(repo_root)

    changed_paths = [Path(p) for p in args.changed]
    deleted_paths = [Path(p) for p in args.deleted]

    # Resolved absolute paths for --changed (same-commit exception + deleted overlap guard)
    changed_abs: set[Path] = {p.resolve() for p in changed_paths}

    total_errors = 0
    total_warnings = 0
    files_checked = 0

    # ── Check WikiLinks in --changed files ────────────────────────────────
    for path in changed_paths:
        if not path.exists():
            print(f"WARNING: {path}: ファイルが見つかりません（スキップ）")
            total_warnings += 1
            continue

        files_checked += 1

        try:
            rel_str = str(path.relative_to(repo_root))
        except ValueError:
            rel_str = str(path)

        lang = get_lang(path, primary_lang)
        wikilinks = extract_wikilinks(path)

        for type_name, slug in wikilinks:
            lang_path = entity_dir / lang / type_name / f"{slug}.md"
            primary_path = entity_dir / primary_lang / type_name / f"{slug}.md"

            lang_path_abs = lang_path.resolve()
            primary_path_abs = primary_path.resolve()

            if lang_path_abs in changed_abs or primary_path_abs in changed_abs:
                # Same-commit new addition — but still block links to pages being removed
                target = lang_path if lang_path_abs in changed_abs else primary_path
                if is_removed(target):
                    msg = f"[[{type_name}/{slug}]] → status: removed のページへのリンクです"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                continue

            if lang_path.exists():
                if is_removed(lang_path):
                    msg = f"[[{type_name}/{slug}]] → status: removed のページへのリンクです"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                # else: link is valid
            elif lang != primary_lang and primary_path.exists():
                if is_removed(primary_path):
                    msg = f"[[{type_name}/{slug}]] → status: removed のページへのリンクです"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                else:
                    msg = f"[[{type_name}/{slug}]] → {primary_lang} のみ存在します（翻訳ページ未作成）"
                    print(f"WARNING: {rel_str}: {msg}")
                    _emit_annotation("warning", "wikilink-no-translation", f"{rel_str}: {msg}", rel_str)
                    total_warnings += 1
            else:
                # Issue #340: downgraded from ERROR to WARNING. Blocking this case
                # pushed both LLM and human authors toward leaving not-yet-created
                # concepts as plain text instead of WikiLinks, so recurring concepts
                # (e.g. benchmark names mentioned across multiple sources) never
                # accumulated enough signal to get their own page. check_wanted_pages.py
                # now surfaces these as a non-blocking report instead.
                msg = f"[[{type_name}/{slug}]] → ページが存在しません"
                print(f"WARNING: {rel_str}: {msg}")
                _emit_annotation("warning", "wikilink-missing", f"{rel_str}: {msg}", rel_str)
                total_warnings += 1

    # ── Build backlink index once for all --deleted checks ────────────────
    backlink_index: dict[str, list[str]] = {}
    if deleted_paths and entity_dir.exists():
        for wiki_page in sorted(entity_dir.rglob("*.md")):
            if "assets" in wiki_page.parts:
                continue
            try:
                content = wiki_page.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                ref_str = str(wiki_page.relative_to(repo_root))
            except ValueError:
                ref_str = str(wiki_page)
            for wl_type, wl_slug in WIKILINK_RE.findall(content):
                key = f"{wl_type}/{wl_slug}"
                refs = backlink_index.setdefault(key, [])
                if ref_str not in refs:
                    refs.append(ref_str)

    # ── Check --deleted files for remaining backlinks ──────────────────────
    for del_path in deleted_paths:
        # If also in --changed (by resolved path), WikiLink check takes priority
        if del_path.resolve() in changed_abs:
            continue

        try:
            del_rel_str = str(del_path.relative_to(repo_root))
        except ValueError:
            del_rel_str = str(del_path)

        # Derive the WikiLink key (Type/slug) from the file path
        resolved = type_slug_from_wiki_path(del_path, entity_dir)
        if resolved is None:
            msg = "entity_dir 配下のパスとして解決できないため被リンクチェックをスキップします"
            print(f"WARNING: {del_rel_str}: {msg}")
            _emit_annotation("warning", "wikilink-unresolvable-path", f"{del_rel_str}: {msg}", del_rel_str)
            total_warnings += 1
            continue
        type_name, slug = resolved
        wikilink_key = f"{type_name}/{slug}"

        for ref_str in backlink_index.get(wikilink_key, []):
            msg = f"被リンクが残っています ({ref_str})"
            print(f"WARNING: {del_rel_str} (status: removed への変更): {msg}")
            _emit_annotation(
                "warning", "wikilink-backlink-remaining",
                f"{del_rel_str}: {msg}", del_rel_str
            )
            total_warnings += 1

    print(f"OK: {files_checked} files checked, {total_errors} errors, {total_warnings} warnings")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
