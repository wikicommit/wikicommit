#!/usr/bin/env python3
"""Detect WikiLinks that reference pages with no page file in any language ("wanted pages").

Counterpart to check_orphans.py: that script finds pages with zero backlinks;
this one finds links with zero backing pages. check_wikilinks.py's "target
page doesn't exist" case was downgraded from ERROR to WARNING (Issue #340) so
authors would stop avoiding WikiLinks for not-yet-created concepts — but that
also meant a concept referenced across many sources no longer surfaced
anywhere on its own. This script restores that visibility as a non-blocking
report, aggregated across the whole wiki (not just a changed-files diff).

Known limitation (Issue #318): a concept that's only ever mentioned in plain
text (never inside a [[Type/slug]] WikiLink) is invisible to this script.

Usage:
    python .wikicommit/scripts/check_wanted_pages.py

Exit code: always 0 (warning-only, non-blocking).
"""

import sys
from pathlib import Path

from _wikilink import ENTITY_DIR, WIKILINK_RE, parse_wiki_path


def collect_pages() -> list[Path]:
    if not ENTITY_DIR.exists():
        return []
    return sorted(p for p in ENTITY_DIR.rglob("*.md") if "assets" not in p.parts)


def main() -> int:
    pages = collect_pages()

    # A key exists as long as some file backs it, in any language, regardless
    # of its status: removed — that's a different failure mode, already
    # handled by check_wikilinks.py's ERROR case for removed-page links.
    existing_keys: set[str] = set()
    referrers: dict[str, list[str]] = {}

    for page in pages:
        resolved = parse_wiki_path(page, ENTITY_DIR)
        if resolved is not None:
            _, type_name, slug = resolved
            existing_keys.add(f"{type_name}/{slug}")

        try:
            content = page.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"WARNING: {page}: ファイルを読み込めませんでした: {e}", file=sys.stderr)
            continue

        ref_str = str(page)
        for type_name, slug in WIKILINK_RE.findall(content):
            key = f"{type_name}/{slug}"
            refs = referrers.setdefault(key, [])
            if ref_str not in refs:
                refs.append(ref_str)

    wanted_count = 0
    for key in sorted(referrers):
        if key in existing_keys:
            continue
        refs = referrers[key]
        print(f"WANTED: {key} (referenced by {len(refs)} pages: {', '.join(refs)})")
        print(f"page: {key}")
        wanted_count += 1

    print(f"SUMMARY: wanted={wanted_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
