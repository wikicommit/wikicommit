#!/usr/bin/env python3
"""Detect orphan pages and duplicate pages in the wiki.

Usage:
    python .wikicommit/scripts/check_orphans.py

Exit code: 0 = no duplicates, 1 = at least one duplicate found.
"""

import os
import sys
import unicodedata
from pathlib import Path

from _frontmatter import parse_frontmatter_text
from _wikilink import ENTITY_DIR, WIKILINK_RE, parse_wiki_path

IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def _emit_annotation(level: str, title: str, message: str, file_path: str | None = None) -> None:
    if IN_GITHUB_ACTIONS:
        loc = f"file={file_path}," if file_path else ""
        print(f"::{level} {loc}title={title}::{message}")


def normalize_title(title: str) -> str:
    t = unicodedata.normalize("NFKC", title)
    return " ".join(t.lower().split())


def _parse_page(path: Path) -> tuple[dict, set[str]]:
    """Return (frontmatter dict, WikiLink keys found anywhere in the file including frontmatter values)."""
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        print(f"WARNING: {path}: ファイルを読み込めませんでした: {e}", file=sys.stderr)
        return {}, set()
    fm, err = parse_frontmatter_text(content)
    if err:
        print(f"WARNING: {path}: {err}", file=sys.stderr)
        fm = {}
    wikilinks = {f"{t}/{s}" for t, s in WIKILINK_RE.findall(content)}
    return fm, wikilinks


def _path_to_wikilink_key(path: Path) -> str:
    """Convert .wikicommit/entity/<lang>/<Type>/<slug>.md to <Type>/<slug>.

    <Type> may contain "/" for nested custom types (e.g. custom/Decision).
    """
    resolved = parse_wiki_path(path, ENTITY_DIR)
    if resolved is None:
        return ""
    _, type_name, slug = resolved
    return f"{type_name}/{slug}"


def collect_pages() -> list[Path]:
    if not ENTITY_DIR.exists():
        return []
    return sorted(p for p in ENTITY_DIR.rglob("*.md") if "assets" not in p.parts)


def main() -> int:
    pages = collect_pages()

    page_data: dict[Path, dict] = {}
    for page in pages:
        fm, wikilinks = _parse_page(page)
        page_data[page] = {"fm": fm, "wikilinks": wikilinks, "key": _path_to_wikilink_key(page)}

    referenced: set[str] = set()
    for path, data in page_data.items():
        if path.name == "index.md":
            continue
        referenced.update(data["wikilinks"])

    orphan_count = 0
    duplicate_count = 0

    for path, data in page_data.items():
        fm = data["fm"]
        if fm.get("status") == "removed":
            continue
        if path.name == "index.md":
            continue
        key = data["key"]
        if not key:
            continue
        if key not in referenced:
            print(f"ORPHAN: {path}")
            _emit_annotation("warning", "orphan", f"orphan page: {path}", str(path))
            orphan_count += 1

    seen: dict[tuple[str, str, str], list[Path]] = {}
    for path, data in page_data.items():
        fm = data["fm"]
        if fm.get("status") == "removed":
            continue
        lang = fm.get("lang", "")
        type_ = fm.get("type", "")
        title = fm.get("title", "")
        if not (lang and type_ and title):
            continue
        key = (str(lang), str(type_), normalize_title(str(title)))
        seen.setdefault(key, []).append(path)

    for paths in seen.values():
        if len(paths) < 2:
            continue
        title_str = str(page_data[paths[0]]["fm"].get("title", ""))
        for path_b in paths[1:]:
            print(f'DUPLICATE: {paths[0]} <-> {path_b} (title: "{title_str}")')
            _emit_annotation("error", "duplicate", f'duplicate title "{title_str}": {paths[0]} <-> {path_b}', str(paths[0]))
            duplicate_count += 1

    print(f"SUMMARY: orphans={orphan_count}, duplicates={duplicate_count}")

    return 1 if duplicate_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
