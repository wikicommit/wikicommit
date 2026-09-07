#!/usr/bin/env python3
"""Detect WikiLinks that reference pages with no page file in any language ("wanted pages").

Counterpart to check_orphans.py: that script finds pages with zero backlinks;
this one finds links with zero backing pages. check_wikilinks.py's "target
page doesn't exist" case was downgraded from ERROR to WARNING (Issue #340) so
authors would stop avoiding WikiLinks for not-yet-created concepts — but that
also meant a concept referenced across many sources no longer surfaced
anywhere on its own. This script restores that visibility as a non-blocking
report, aggregated across the whole wiki (not just a changed-files diff).

A link that names an existing page's slug under the wrong Type looks identical
to a not-yet-written page from here, so it is separated out as TYPE_MISMATCH
rather than counted as WANTED (Issue #563) — creating the "wanted" page would
duplicate one that already exists; the fix is to correct the link's Type.

Known limitation (Issue #318): a concept that's only ever mentioned in plain
text (never inside a [[Type/slug]] WikiLink) is invisible to this script.

Usage:
    python .wikicommit/scripts/check_wanted_pages.py

Exit code: always 0 (warning-only, non-blocking).
"""

import sys
from pathlib import Path

from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    build_slug_type_index,
    collect_entity_pages,
    collect_view_pages,
    other_types_for_slug,
    parse_view_path,
    parse_wiki_path,
)


def collect_pages() -> list[Path]:
    # include_index=True: a Type index is both a referrer and a backing file
    # here, as it was before this walk was shared. Whether a stale index entry
    # should count as "someone wants this page written" is a separate question
    # from consolidating the walk, so it is left as it was (Issue #677).
    #
    # View pages (Issue #675) count on both sides: they link out like any
    # page, and `[[View/<slug>]]` resolves to one, so leaving them out would
    # report every existing view page as wanted.
    return collect_entity_pages(ENTITY_DIR, include_index=True) + collect_view_pages(
        VIEW_DIR, include_index=True
    )


def main() -> int:
    pages = collect_pages()

    # A key exists as long as some file backs it, in any language, regardless
    # of its status: removed — that's a different failure mode, already
    # handled by check_wikilinks.py's ERROR case for removed-page links.
    existing_keys: set[str] = set()
    referrers: dict[str, list[str]] = {}

    for page in pages:
        resolved = parse_wiki_path(page, ENTITY_DIR) or parse_view_path(page, VIEW_DIR)
        if resolved is not None:
            _, type_name, slug = resolved
            existing_keys.add(f"{type_name}/{slug}")

        try:
            content = page.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"WARNING: {page}: could not be read: {e}", file=sys.stderr)
            continue

        ref_str = str(page)
        for type_name, slug in WIKILINK_RE.findall(content):
            key = f"{type_name}/{slug}"
            refs = referrers.setdefault(key, [])
            if ref_str not in refs:
                refs.append(ref_str)

    # A link whose slug already has a page under a different Type is not a page
    # anyone should create — acting on a WANTED: line for it produces a second
    # page duplicating the first, which check_orphans.py's duplicate detection
    # (same lang, same title AND same type) does not catch either. Report it as
    # its own kind of finding instead (Issue #563).
    #
    # Built on first use, and only once some link fails to resolve: the index
    # costs a second full walk of .wikicommit/entity/ (plus a frontmatter parse
    # per page) on top of the one above, and a wiki whose links all resolve
    # should not pay for one nothing goes on to read — same reasoning as
    # check_wikilinks.py's lazy build of the same index.
    slug_index: dict[str, set[str]] | None = None

    wanted_count = 0
    type_mismatch_count = 0
    for key in sorted(referrers):
        if key in existing_keys:
            continue
        refs = referrers[key]
        type_name, _, slug = key.rpartition("/")
        if slug_index is None:
            slug_index = build_slug_type_index(ENTITY_DIR)
        other_types = other_types_for_slug(type_name, slug, slug_index)
        if other_types:
            found = ", ".join(f"{t}/{slug}.md" for t in other_types)
            print(
                f"TYPE_MISMATCH: {key} has no page, but the same slug exists at {found}"
                f" (referenced by {len(refs)} pages: {', '.join(refs)})"
            )
            print(f"page: {key}")
            type_mismatch_count += 1
            continue
        print(f"WANTED: {key} (referenced by {len(refs)} pages: {', '.join(refs)})")
        print(f"page: {key}")
        wanted_count += 1

    print(f"SUMMARY: wanted={wanted_count}, type_mismatch={type_mismatch_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
