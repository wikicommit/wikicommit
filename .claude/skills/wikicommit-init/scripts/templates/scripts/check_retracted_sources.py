#!/usr/bin/env python3
"""Detect wiki pages still resting on a source a human has retracted (Issue #737).

`status: retracted` says a human read a registered source, judged its content
unreliable, and took it out of use. Doing that stops the source from being
ingested again — `add_source.py` returns `RETRACTED` instead of re-registering
it, and `check_ingest_freshness.py` never rewrites it back to `outdated` — but
it does nothing to the pages that were already written from it. Those pages
keep the source in their `sources[]`, unchanged and unremarked.

This script closes that gap by reporting, not by acting. Issue #737 settled
deliberately on "report and stop there", for two reasons:

- Resetting `review_status` to `pending` does not fit the rule Issue #724 laid
  down. That rule delegates "did the content actually change?" to a
  deterministic script and keeps a non-deterministic judgment out of deciding
  whether a human has to re-read a page. A retraction changes no content at
  all — it changes the standing of the evidence behind it — so the same
  machinery cannot express it.
- Even if a page were reset, `pending` says "read this again" and not "here is
  what is now unsupported". The tracking-Issue template does not ask about the
  soundness of a page's sources, which is where Issue #737 started.

Which of the existing routes to take is a human's call:

- `/wikicommit-generate --regenerate <page>` rebuilds from the sources that
  remain, dropping the retracted one and its entry in `sources[]` (Issue #744).
  This is the route that actually takes a retracted source out of a page's
  evidence base, and it needs at least one surviving source. Two counts differ
  here: Regeneration Mode excludes any page carrying a `type: manual` entry
  outright, while the remaining count below deliberately counts one as a
  surviving source, so a page whose only remainder is a human assertion is a
  `/wikicommit-fix` rather than a rebuild.
- `/wikicommit-fix` corrects the text by hand, for a page whose problem is
  narrower than a rebuild.
- `/wikicommit-remove` takes the page down, which is the answer when nothing is
  left holding it up.

This script's whole job is to give a human enough to choose between them: which
pages, resting on which retracted source, and how much else those pages have to
stand on — the last of which is why every finding carries a remaining count.

Both trees are scanned. A view page carries `derived_from` rather than
`sources[]`, so it can never match directly, but it is not therefore safe:
it is built out of entity pages, and one of those may be the page resting on
the retracted source. That indirection is out of scope here —
`check_derivation_freshness.py` is the script that follows `derived_from`, and
it fires when a grounding page is actually rewritten.

Usage:
    python .wikicommit/scripts/check_retracted_sources.py

Exit code: always 0 (informational, non-blocking).
"""

import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_or_warn
from _wikilink import ENTITY_DIR, VIEW_DIR, collect_entity_pages, collect_view_pages

SOURCE_DIR = Path(".wikicommit/source")


def collect_retracted_sources(source_dir: Path = SOURCE_DIR) -> dict[str, str]:
    """Map each retracted source's identity (`source.path` or `source.url`) to
    its management file path.

    The identity key is the same one `add_source.py` matches on when it decides
    whether a source is already registered (Issue #572 / #573), which is also
    the value a page's `sources[]` entry carries. Keying on anything else —
    the derived management-file name, say — would miss management files written
    under an older naming rule, since those are never migrated.
    """
    retracted: dict[str, str] = {}
    if not source_dir.exists():
        return retracted

    for mgmt_file in sorted(source_dir.rglob("*.md")):
        fm = parse_frontmatter_or_warn(mgmt_file)
        if not fm or fm.get("status") != "retracted":
            continue
        source = fm.get("source")
        if not isinstance(source, dict):
            continue
        for key in ("path", "url"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                retracted[value.strip()] = str(mgmt_file)
    return retracted


def page_source_entries(fm: dict) -> list[list[str]]:
    """Return, one list per `sources[]` entry, the `path`/`url` identities it names.

    Grouped per entry rather than flattened so the caller can count *entries*.
    A `type: manual` entry names neither a path nor a url — it carries
    `author`/`created_at` instead — so it contributes an empty list here and
    would vanish entirely from a flat identity count. That
    matters because the count is reported as "N other source(s) remain on this
    page", and `wikicommit-status` Step 12 reads zero as "nothing left holding
    it up and is usually a /wikicommit-remove": a page whose only surviving
    source is a human assertion must not be pushed toward deletion.
    """
    sources = fm.get("sources")
    if not isinstance(sources, list):
        return []
    entries: list[list[str]] = []
    for entry in sources:
        if not isinstance(entry, dict):
            continue
        identities = []
        for key in ("path", "url"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                identities.append(value.strip())
        entries.append(identities)
    return entries


def main() -> int:
    retracted = collect_retracted_sources()
    if not retracted:
        # Say so rather than printing a bare zero: on a wiki that has never
        # retracted anything, "0 affected pages" and "nothing was retracted"
        # look identical, and only the second one means the check had nothing
        # to look for.
        print("SUMMARY: retracted_sources=0, affected_pages=0")
        return 0

    pages = collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)

    affected = 0
    for page in sorted(pages):
        fm = parse_frontmatter_or_warn(page)
        if not fm or fm.get("status") == "removed":
            continue
        entries = page_source_entries(fm)
        hits = sorted({i for entry in entries for i in entry if i in retracted})
        if not hits:
            continue
        affected += 1
        # Count entries with no retracted identity, so a `type: manual` entry
        # (which names no identity at all) still counts as a source the page
        # rests on, and a page that happens to list the same source twice is
        # not reported twice.
        remaining = sum(1 for entry in entries if not any(i in retracted for i in entry))
        for identity in hits:
            print(
                f"RETRACTED_SOURCE: {page}: sources[] still names {identity} "
                f"(retracted in {retracted[identity]}); "
                f"{remaining} other source(s) remain on this page"
            )
        print(f"page: {page}")

    print(f"SUMMARY: retracted_sources={len(retracted)}, affected_pages={affected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
