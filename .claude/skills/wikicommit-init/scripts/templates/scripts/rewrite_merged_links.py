#!/usr/bin/env python3
"""rewrite_merged_links.py — point WikiLinks at the page a removed page was merged into (Issue #1119).

When pages are merged, the absorbed ones are taken down with
`removed_reason: merged` and `merged_into: <kept page>`. Every link to them is
then a link to a `status: removed` page, which `check_wikilinks.py` blocks —
deliberately: the quality gate's asymmetry (removing a page only warns, adding a
link to a removed one blocks) is what keeps a removed page from quietly coming
back. So the links are rewritten in the pages themselves, `[[Type/old]]` to
`[[Type/new]]`, rather than redirected at publish time, which would carve an
exception into that asymmetry.

The map is read from disk, not passed in: every page at `status: removed` with a
`merged_into` contributes `<its Type/slug> -> <merged_into's Type/slug>`, and
chains (A merged into B, later B into C) are followed to the end. A Type/slug is
left alone, with a WARNING, when some language still has it live (a link to it
still resolves there), when its removed versions name different targets, or
when following it loops.

Every live page under `.wikicommit/entity/` and `.wikicommit/view/` is rewritten —
the body, and the frontmatter too, where `properties:` values carry WikiLinks.
`index.md` is skipped: `rebuild_index.py` rewrites it from the pages. Only the
link text changes; nothing else in the file is touched, and a page's
`review_status` is kept (the link now names the page a person decided is the
same concept — the claim around it is unchanged). For the same reason
`check_review_coverage.py` does not report the rewrite as `STALE_REVIEW:`: it
undoes each merge recorded in `relations.yml` before deciding a page changed.

    REWRITTEN: <path> (<N> link(s))
    SUMMARY: merged=<N>, pages=<N>, links=<N>

`--dry-run` prints the same lines and writes nothing.

Exit code: 0 always.
"""

import argparse
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    collect_view_pages,
    normalize_entity_prefix,
    parse_view_path,
    parse_wiki_path,
)


def ident_of(path: Path) -> str | None:
    parsed = parse_wiki_path(path, ENTITY_DIR) or parse_view_path(path, VIEW_DIR)
    if parsed is None:
        return None
    _, type_name, slug = parsed
    return f"{type_name}/{slug}"


def frontmatter(path: Path) -> dict:
    fm, _ = parse_frontmatter(path)
    return fm if isinstance(fm, dict) else {}


def build_map(pages: list[Path]) -> dict[str, str]:
    """Type/slug -> the Type/slug it was merged into, after following chains."""
    targets: dict[str, set[str]] = {}
    live: set[str] = set()
    for page in pages:
        ident = ident_of(page)
        if ident is None:
            continue
        fm = frontmatter(page)
        if fm.get("status") != "removed":
            live.add(ident)
            continue
        stored = fm.get("merged_into")
        if not isinstance(stored, str) or not stored.strip():
            continue
        target = ident_of(Path(normalize_entity_prefix(stored.strip().replace("\\", "/"))))
        if target is None:
            print(f"WARNING: {page.as_posix()}: merged_into {stored!r} is not a page path, ignored", file=sys.stderr)
            continue
        targets.setdefault(ident, set()).add(target)

    direct: dict[str, str] = {}
    for ident, found in sorted(targets.items()):
        if ident in live:
            print(f"WARNING: [[{ident}]] is merged in one language but still live in another; "
                  "links to it are left as they are", file=sys.stderr)
        elif len(found) > 1:
            print(f"WARNING: [[{ident}]] is merged into more than one page ({', '.join(sorted(found))}); "
                  "links to it are left as they are", file=sys.stderr)
        else:
            direct[ident] = next(iter(found))

    resolved: dict[str, str] = {}
    for ident in direct:
        seen = {ident}
        target = direct[ident]
        while target in direct:
            if target in seen:
                print(f"WARNING: merged_into loops through [[{ident}]]; links to it are left as they are",
                      file=sys.stderr)
                target = None
                break
            seen.add(target)
            target = direct[target]
        if target is not None:
            resolved[ident] = target
    return resolved


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Rewrite WikiLinks to merged pages to the page they were merged into.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    pages = [*collect_entity_pages(ENTITY_DIR), *collect_view_pages(VIEW_DIR)]
    mapping = build_map(pages)
    rewritten_pages = rewritten_links = 0
    for page in pages:
        if mapping == {} or frontmatter(page).get("status") == "removed":
            continue
        # Read as plain UTF-8 so a leading BOM stays in `text` and is written back:
        # only the link text may change.
        with page.open(encoding="utf-8", newline="") as f:
            text = f.read()
        count = 0

        def swap(match):
            nonlocal count
            target = mapping.get(f"{match.group(1)}/{match.group(2)}")
            if target is None:
                return match.group(0)
            count += 1
            return f"[[{target}]]"

        new_text = WIKILINK_RE.sub(swap, text)
        if count == 0:
            continue
        if not args.dry_run:
            with page.open("w", encoding="utf-8", newline="") as f:
                f.write(new_text)
        rewritten_pages += 1
        rewritten_links += count
        print(f"REWRITTEN: {page.as_posix()} ({count} link(s))")
    print(f"SUMMARY: merged={len(mapping)}, pages={rewritten_pages}, links={rewritten_links}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
