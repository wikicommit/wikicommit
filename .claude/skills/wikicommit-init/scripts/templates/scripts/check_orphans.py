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
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    collect_view_pages,
    parse_wiki_path,
)

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
        print(f"WARNING: {path}: could not be read: {e}", file=sys.stderr)
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
    return collect_entity_pages(ENTITY_DIR)


def collect_link_sources() -> list[Path]:
    """Pages whose outbound WikiLinks count as backlinks, which is a wider set
    than the pages this script can *report* on.

    View pages (Issue #675) are excluded from the orphan report itself — one is
    unlinked the moment it is written, so every one of them would be a finding
    nobody can act on — but their links are ordinary links. Leaving them out of
    the backlink set would mean moving a synthesized page from
    `.wikicommit/entity/` into `.wikicommit/view/` silently turns each page it
    references back into an orphan, and `check_wanted_pages.py` (which walks
    both trees) would disagree with this script about the same repository.
    """
    return collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)


def source_labels(frontmatter: dict) -> list[str]:
    """Short identifiers for a page's `sources`, for the ORPHAN line (Issue #570).

    An orphan is a page nothing links to, and the useful next question is which
    source produced it — a `wikicommit/saitama-city-wiki` audit found all six of
    its orphans came from sources that had produced no other page, while pages
    from the two sources covering the subject's overall structure were reachable
    throughout. That is one repository and partly self-fulfilling (a structural
    source links to everything by definition), so it is a hypothesis rather than
    a finding; printing the provenance is what makes it checkable at all.
    """
    sources = frontmatter.get("sources")
    if not isinstance(sources, list):
        return []
    labels = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        value = entry.get("path") or entry.get("url") or entry.get("author")
        if isinstance(value, str) and value.strip():
            labels.append(value.strip())
    return labels


def main() -> int:
    pages = collect_pages()

    page_data: dict[Path, dict] = {}
    for page in pages:
        fm, wikilinks = _parse_page(page)
        page_data[page] = {"fm": fm, "wikilinks": wikilinks, "key": _path_to_wikilink_key(page)}

    referenced: set[str] = set()
    for page in collect_link_sources():
        data = page_data.get(page)
        if data is None:
            _, wikilinks = _parse_page(page)
        else:
            wikilinks = data["wikilinks"]
        referenced.update(wikilinks)

    orphan_count = 0
    duplicate_count = 0

    for path, data in page_data.items():
        fm = data["fm"]
        if fm.get("status") == "removed":
            continue
        key = data["key"]
        if not key:
            continue
        if key not in referenced:
            labels = source_labels(fm)
            origin = f" (sources: {', '.join(labels)})" if labels else " (no sources)"
            print(f"ORPHAN: {path}{origin}")
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
