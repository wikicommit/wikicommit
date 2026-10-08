#!/usr/bin/env python3
"""remove_page.py — wikicommit-remove のバックエンドスクリプト。

対象ページに status: removed / removed_at / removed_reason（/ merged_into）を付与する。
対象ページを親（translated_from）に持つ翻訳ページも同時に検出して同様に処理する。
影響を受けた Type ディレクトリ（view ページの場合は言語ディレクトリ）の index.md から
該当エントリを削除する。

物理ファイル削除は行わない（status: removed によるソフト削除設計のため）。

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

sys.path.insert(0, str(Path(__file__).parent))
from _frontmatter import parse_frontmatter as _parse_frontmatter  # noqa: E402
from _wikilink import (  # noqa: E402
    normalize_entity_prefix,
    parse_view_path,
    parse_wiki_path,
)

FRONTMATTER_RE = re.compile(r"^(---\r?\n)(.*?)((?:\r?\n)?---\r?\n?)", re.DOTALL)
VALID_REASONS = ("obsolete", "merged", "gdpr")


def parse_frontmatter(path: Path) -> dict:
    """ページの frontmatter を dict として返す。読めない・パース不能なら {} を返す。

    読み取りは共有の `_frontmatter.py` に任せる。このスクリプトは `.wikicommit/scripts/` に
    あり、同じディレクトリの共有モジュールを import できる（Issue #1210 で Skill 内から
    移した。それまでは自己完結の慣行で写しを持っていた）。
    """
    fm, _err = _parse_frontmatter(path)
    return fm or {}


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


def find_view_translation_pages(view_dir: Path, target_rel: str, exclude: Path) -> list[Path]:
    """target_rel を translated_from に持つ view ページの翻訳を全言語から探索する。

    view ツリーには Type ディレクトリが無いため、entity 側の
    `*/<Type>/*.md` に相当する glob は `*/*.md` になる。
    """
    if not view_dir.exists():
        return []
    results = []
    for candidate in sorted(view_dir.glob("*/*.md")):
        if candidate.name == "index.md" or candidate.resolve() == exclude.resolve():
            continue
        fm = parse_frontmatter(candidate)
        translated_from = fm.get("translated_from")
        if not translated_from:
            continue
        stored = normalize_entity_prefix(str(translated_from).strip().replace("\\", "/"))
        if stored == target_rel:
            results.append(candidate)
    return results


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
    """index.md から `[[<type>/<slug>]]` の行を削除する。削除した場合 True を返す。

    rebuild_index.py が書く現在の書式は `- [[<type>/<slug>]]`（Issue #678。それ以前は
    リストマーカーなしで、さらに ` — <title>` の接尾辞が付いていた）。ここは3形式すべてを
    受けるため、先頭のリストマーカーを任意扱いにし、行末までを捨てる — 既存リポジトリの
    index.md は次回 rebuild_index.py が走るまで旧書式のまま残る（遡及移行を行わない方針）。
    """
    content = index_path.read_text(encoding="utf-8-sig")
    escaped = re.escape(f"[[{type_name}/{slug}]]")
    pattern = re.compile(rf"^[ \t]*(?:[-*+][ \t]+)?{escaped}.*\r?\n?", re.MULTILINE)
    new_content, count = pattern.subn("", content)
    if count:
        new_content = _drop_empty_sections(new_content)
        index_path.write_text(new_content, encoding="utf-8")
    return count > 0


_SECTION_HEADING_RE = re.compile(r"^##[ \t]")


def _drop_empty_sections(content: str) -> str:
    """Drop `## ` headings left with nothing under them (Issue #1136).

    A Type with a groups file has an index split into `## <label>` sections
    (rebuild_index.py's `_grouped_body()`, Issue #1035), and rebuild_index.py
    leaves out any section with no page — a group, or the unclassified section.
    Removing a section's last row here would otherwise leave its heading
    standing over nothing until rebuild_index.py next runs. A section counts as
    empty when only blank lines follow its heading up to the next `## ` heading
    or the end of the file; the heading goes with those blank lines, and the
    file is left ending in a single newline as rebuild_index.py writes it.
    """
    lines = content.splitlines(keepends=True)
    kept: list[str] = []
    i = 0
    while i < len(lines):
        if _SECTION_HEADING_RE.match(lines[i]):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j == len(lines) or _SECTION_HEADING_RE.match(lines[j]):
                i = j
                continue
        kept.append(lines[i])
        i += 1
    result = "".join(kept)
    if result != content:
        stripped = result.rstrip("\r\n")
        result = stripped + "\n" if stripped else ""
    return result


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
        print(f"ERROR: {args.page}: path is outside the repository", file=sys.stderr)
        return 1

    if not page_path.is_file():
        print(f"ERROR: {args.page}: file does not exist", file=sys.stderr)
        return 1

    fm = parse_frontmatter(page_path)
    if fm.get("status") == "removed":
        print(f"ERROR: {args.page}: already has status: removed", file=sys.stderr)
        return 1

    if args.reason == "merged" and not args.merged_into:
        print("ERROR: --merged-into is required when --reason merged is given", file=sys.stderr)
        return 1

    merged_into = args.merged_into
    if merged_into:
        if not (repo_root / merged_into).is_file():
            print(f"ERROR: the file given to --merged-into does not exist: {merged_into}", file=sys.stderr)
            return 1

    if args.today:
        try:
            today = datetime.date.fromisoformat(args.today).isoformat()
        except ValueError:
            print(f"ERROR: --today: invalid date format: {args.today}", file=sys.stderr)
            return 1
    else:
        today = datetime.date.today().isoformat()

    entity_dir = repo_root / ".wikicommit" / "entity"
    view_dir = repo_root / ".wikicommit" / "view"
    fields = removed_fields(today, args.reason, merged_into)

    try:
        apply_removed_fields_to_file(page_path, fields)
    except ValueError:
        print(f"ERROR: {args.page}: no frontmatter found", file=sys.stderr)
        return 1

    removed_paths = [page_path]

    resolved = parse_wiki_path(page_path, entity_dir)
    if resolved is not None:
        _, type_name, _slug = resolved
        target_rel = str(page_path.relative_to(repo_root)).replace("\\", "/")
        for translation_path in find_translation_pages(entity_dir, type_name, target_rel, exclude=page_path):
            apply_removed_fields_to_file(translation_path, fields)
            removed_paths.append(translation_path)
    elif parse_view_path(page_path, view_dir) is not None:
        target_rel = str(page_path.relative_to(repo_root)).replace("\\", "/")
        for translation_path in find_view_translation_pages(view_dir, target_rel, exclude=page_path):
            apply_removed_fields_to_file(translation_path, fields)
            removed_paths.append(translation_path)

    for path in removed_paths:
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        print(f"REMOVED: {rel}")

    for path in removed_paths:
        resolved = parse_wiki_path(path, entity_dir)
        if resolved is not None:
            lang, type_name, slug = resolved
            index_path = entity_dir / lang / type_name / "index.md"
        else:
            resolved = parse_view_path(path, view_dir)
            if resolved is None:
                continue
            # view ページの index は言語ディレクトリ直下にある（Type ディレクトリを挟まない）。
            lang, type_name, slug = resolved
            index_path = view_dir / lang / "index.md"
        if index_path.is_file():
            remove_index_entry(index_path, type_name, slug)

    print(f"SUMMARY: removed={len(removed_paths)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
