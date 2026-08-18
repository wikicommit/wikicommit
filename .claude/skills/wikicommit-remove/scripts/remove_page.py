#!/usr/bin/env python3
"""remove_page.py — wikicommit-remove のバックエンドスクリプト。

対象ページに status: removed / removed_at / removed_reason（/ merged_into）を付与する。
対象ページを親（translated_from）に持つ翻訳ページも同時に検出して同様に処理する。
影響を受けた Type ディレクトリの index.md から該当エントリを削除する。

物理ファイル削除は行わない（DesignDoc-data.md §4.5 のソフト削除設計）。

Usage:
    python remove_page.py <page> --reason <obsolete|merged|gdpr> [--merged-into <path>] [--today=YYYY-MM-DD]

Exit code:
    0 = success
    1 = <page> が存在しない / 既に status: removed / --reason merged なのに
        --merged-into 未指定 / --merged-into の指すファイルが存在しない /
        --today の形式が不正
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^(---\r?\n)(.*?)((?:\r?\n)?---\r?\n?)", re.DOTALL)
VALID_REASONS = ("obsolete", "merged", "gdpr")

LEGACY_ENTITY_PREFIX = ".wikicommit/wiki/"
ENTITY_PREFIX = ".wikicommit/entity/"


def normalize_entity_prefix(raw_path: str) -> str:
    """Rewrite a stored page path's pre-Issue-#477 `.wikicommit/wiki/`
    prefix to the current `.wikicommit/entity/` one, for comparing a
    translation page's `translated_from` against a freshly-computed
    `.wikicommit/entity/...` path regardless of which prefix the stored
    value happens to use (no auto-migration — docs/DesignDoc-data.md §4.3's
    coexistence precedent). Mirrors .wikicommit/scripts/_wikilink.py's
    helper of the same name — duplicated here rather than imported because
    this Skill script runs as a subprocess and can't assume
    .wikicommit/scripts/ is resolvable relative to its caller's cwd."""
    if raw_path.startswith(LEGACY_ENTITY_PREFIX):
        return ENTITY_PREFIX + raw_path[len(LEGACY_ENTITY_PREFIX):]
    return raw_path


def parse_frontmatter(path: Path) -> dict:
    """ページの frontmatter を dict として返す。パース不能なら {} を返す。"""
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(2)) or {}
    except yaml.YAMLError:
        return {}


def _upsert_field(yaml_block: str, key: str, value: str) -> str:
    """yaml_block 内の `key: ...` 行を置換、なければ末尾に追加する。"""
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    line = f"{key}: {value}"
    if pattern.search(yaml_block):
        # 文字列として渡すと value 中の "\1" 等がグループ参照として解釈され
        # re.error を招くため、関数として渡してリテラル置換にする。
        return pattern.sub(lambda _m: line, yaml_block, count=1)
    return yaml_block.rstrip("\r\n") + f"\n{line}"


def add_removed_fields(content: str, fields: list[tuple[str, str]]) -> str:
    """frontmatter ブロックに fields を追加・上書きする（本文・書式は保持）。

    pyyaml による frontmatter 再出力はインデント・クォート・キー順序を変えてしまうため、
    正規表現による置換のみを行う（wikicommit-review スクリプトと同じ方針）。
    """
    m = FRONTMATTER_RE.match(content)
    if not m:
        raise ValueError("frontmatter block not found")
    yaml_block = m.group(2)
    delimiter = m.group(3)
    for key, value in fields:
        yaml_block = _upsert_field(yaml_block, key, value)
    if not re.match(r"^\r?\n", delimiter):
        yaml_block += "\n"
    return content[: m.start(2)] + yaml_block + content[m.end(2):]


def apply_removed_fields_to_file(path: Path, fields: list[tuple[str, str]]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as f:
        content = f.read()
    updated = add_removed_fields(content, fields)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(updated)


def removed_fields(today: str, reason: str, merged_into: str | None) -> list[tuple[str, str]]:
    fields = [
        ("status", "removed"),
        ("removed_at", f'"{today}"'),
        ("removed_reason", reason),
    ]
    if merged_into:
        fields.append(("merged_into", merged_into))
    return fields


def parse_wiki_path(path: Path, entity_dir: Path) -> tuple[str, str, str] | None:
    """.wikicommit/entity/<lang>/<Type>/<slug>.md から (lang, type, slug) を導出する。

    Type はカスタム型で "/" を含みうる（例: custom/Decision）。
    """
    try:
        rel = path.resolve().relative_to(entity_dir.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    parts = rel.parts
    if len(parts) < 3:
        return None
    lang = parts[0]
    type_name = "/".join(parts[1:-1])
    slug = parts[-1].removesuffix(".md")
    return lang, type_name, slug


def find_translation_pages(entity_dir: Path, type_name: str, target_rel: str, exclude: Path) -> list[Path]:
    """target_rel を translated_from に持つ翻訳ページを同一 Type ディレクトリ横断で探索する。"""
    if not entity_dir.exists():
        return []
    results = []
    for candidate in sorted(entity_dir.glob(f"*/{type_name}/*.md")):
        if candidate.name == "index.md":
            continue
        if candidate.resolve() == exclude.resolve():
            continue
        fm = parse_frontmatter(candidate)
        translated_from = fm.get("translated_from")
        if translated_from is None:
            continue
        # normalize_entity_prefix() lets a translation page written before the
        # Issue #477 .wikicommit/wiki/ -> entity/ rename (translated_from
        # still verbatim; no auto-migration) match against target_rel, which
        # is always computed from the current (post-rename) tree.
        stored = normalize_entity_prefix(str(translated_from).strip().replace("\\", "/"))
        if stored == target_rel:
            results.append(candidate)
    return results


def remove_index_entry(index_path: Path, type_name: str, slug: str) -> bool:
    """index.md から `[[<type>/<slug>]] — ...` 行を削除する。削除した場合 True を返す。"""
    content = index_path.read_text(encoding="utf-8-sig")
    escaped = re.escape(f"[[{type_name}/{slug}]]")
    pattern = re.compile(rf"^{escaped}.*\r?\n?", re.MULTILINE)
    new_content, count = pattern.subn("", content)
    if count:
        index_path.write_text(new_content, encoding="utf-8")
    return count > 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mark a wiki page (and its translations) as status: removed."
    )
    parser.add_argument("page", help="Path to the wiki page (relative to repo root)")
    parser.add_argument("--reason", required=True, choices=VALID_REASONS)
    parser.add_argument("--merged-into", dest="merged_into", default=None)
    parser.add_argument("--today", default=None, metavar="YYYY-MM-DD")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    page_path = (repo_root / args.page).resolve()

    if not page_path.is_relative_to(repo_root):
        print(f"ERROR: {args.page}: リポジトリ外のパスです", file=sys.stderr)
        return 1

    if not page_path.is_file():
        print(f"ERROR: {args.page}: ファイルが存在しません", file=sys.stderr)
        return 1

    fm = parse_frontmatter(page_path)
    if fm.get("status") == "removed":
        print(f"ERROR: {args.page}: 既に status: removed です", file=sys.stderr)
        return 1

    if args.reason == "merged" and not args.merged_into:
        print("ERROR: --reason merged の場合 --merged-into が必須です", file=sys.stderr)
        return 1

    merged_into = args.merged_into
    if merged_into:
        if not (repo_root / merged_into).is_file():
            print(f"ERROR: --merged-into で指定されたファイルが存在しません: {merged_into}", file=sys.stderr)
            return 1

    if args.today:
        try:
            today = datetime.date.fromisoformat(args.today).isoformat()
        except ValueError:
            print(f"ERROR: --today: 不正な日付形式です: {args.today}", file=sys.stderr)
            return 1
    else:
        today = datetime.date.today().isoformat()

    entity_dir = repo_root / ".wikicommit" / "entity"
    fields = removed_fields(today, args.reason, merged_into)

    try:
        apply_removed_fields_to_file(page_path, fields)
    except ValueError:
        print(f"ERROR: {args.page}: frontmatter が見つかりません", file=sys.stderr)
        return 1

    removed_paths = [page_path]

    resolved = parse_wiki_path(page_path, entity_dir)
    if resolved is not None:
        _, type_name, _slug = resolved
        target_rel = str(page_path.relative_to(repo_root)).replace("\\", "/")
        for translation_path in find_translation_pages(entity_dir, type_name, target_rel, exclude=page_path):
            apply_removed_fields_to_file(translation_path, fields)
            removed_paths.append(translation_path)

    for path in removed_paths:
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        print(f"REMOVED: {rel}")

    for path in removed_paths:
        resolved = parse_wiki_path(path, entity_dir)
        if resolved is None:
            continue
        lang, type_name, slug = resolved
        index_path = entity_dir / lang / type_name / "index.md"
        if index_path.is_file():
            remove_index_entry(index_path, type_name, slug)

    print(f"SUMMARY: removed={len(removed_paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
