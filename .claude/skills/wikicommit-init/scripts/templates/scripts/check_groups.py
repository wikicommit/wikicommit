#!/usr/bin/env python3
"""Report on group files: unclassified pages, stale members, invalid files (Issue #1035).

Usage:
    python .wikicommit/scripts/check_groups.py
    python .wikicommit/scripts/check_groups.py --type <Type> [--limit N]

Without --type: one `TYPE:` line per group file under `.wikicommit/groups/`, plus
an `ERROR:` line for each file that cannot be used. `/wikicommit-status` reads
this. A Type with no group file is not reported at all — reporting it would light
every Type all the time, and a line that is always on stops being read (Issue #562).

With --type: the detail `/wikicommit-organize` needs — each group, each slug the
file names that no longer has a page (`STALE_MEMBER:`), and each page no group
claims (`UNCLASSIFIED:`, up to --limit, as a path `build_survey_view.py --pages`
accepts). A Type with no group file is reported too here, since the question is
then "group everything".

Pages are counted by slug, across languages: a group file covers every language
(the slug is language-neutral), so a page and its translations are one entry.
The path printed is the primary-language page when there is one. Index pages and
`status: removed` pages are never counted.

No threshold: how many unclassified pages are too many has no basis yet, so the
count is reported and the decision left to the reader.

Exit code: always 0 (a report, never a gate — an invalid group file is listed
flat by every reader, so nothing breaks while it waits to be fixed).
"""

import argparse
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _groups import GROUPS_DIR, discover_group_files, group_file_path, load_group_file
from _wikilink import ENTITY_DIR, collect_entity_pages, load_primary_lang, parse_wiki_path


def pages_by_type(entity_dir: Path, primary_lang: str) -> dict[str, dict[str, Path]]:
    """type_name -> slug -> one path (primary language preferred)."""
    found: dict[str, dict[str, Path]] = {}
    for path in collect_entity_pages(entity_dir):
        resolved = parse_wiki_path(path, entity_dir)
        if resolved is None:
            continue
        lang, type_name, slug = resolved
        fm, err = parse_frontmatter(path)
        if not err and (fm or {}).get("status") == "removed":
            continue
        slugs = found.setdefault(type_name, {})
        if slug not in slugs or lang == primary_lang:
            slugs[slug] = path
    return found


def report_all(pages: dict[str, dict[str, Path]]) -> int:
    types = unclassified_total = stale_total = errors = 0
    for type_name, path in discover_group_files(GROUPS_DIR):
        group_file, problems = load_group_file(type_name, GROUPS_DIR)
        if problems:
            errors += 1
            for problem in problems:
                print(f"ERROR: {path.as_posix()}: {problem}")
            continue
        types += 1
        present = pages.get(type_name, {})
        claimed = group_file.group_of()
        unclassified = [s for s in present if s not in claimed]
        stale = [s for s in claimed if s not in present]
        unclassified_total += len(unclassified)
        stale_total += len(stale)
        print(
            f"TYPE: {type_name} groups={len(group_file.groups)}, grouped={len(claimed) - len(stale)}, "
            f"unclassified={len(unclassified)}, stale={len(stale)}"
        )
    print(f"SUMMARY: types={types}, unclassified={unclassified_total}, stale={stale_total}, errors={errors}")
    return 0


def report_type(type_name: str, pages: dict[str, dict[str, Path]], limit: int) -> int:
    present = pages.get(type_name, {})
    path = group_file_path(type_name, GROUPS_DIR)
    group_file, problems = load_group_file(type_name, GROUPS_DIR)
    if problems:
        for problem in problems:
            print(f"ERROR: {path.as_posix()}: {problem}")
        print(f"SUMMARY: type={type_name}, pages={len(present)}, errors={len(problems)}")
        return 0
    claimed = group_file.group_of() if group_file else {}
    if group_file is None:
        print(f"NOTE: {path.as_posix()} does not exist — every page of {type_name} is unclassified")
    else:
        for group in group_file.groups:
            label = ", ".join(f"{k}: {v}" for k, v in sorted(group.label.items())) or "-"
            members = sum(1 for s in group.pages if s in present)
            print(f"GROUP: {group.key} | pages={members} | label={label} | criterion={group.criterion or '-'}")
    for slug, key in claimed.items():
        if slug not in present:
            print(f"STALE_MEMBER: {slug} (group {key}) — no live {type_name} page has this slug")
    unclassified = sorted(s for s in present if s not in claimed)
    shown = unclassified if limit <= 0 else unclassified[:limit]
    for slug in shown:
        print(f"UNCLASSIFIED: {present[slug].as_posix()}")
    if len(shown) < len(unclassified):
        print(f"TRUNCATED: {len(unclassified) - len(shown)} more unclassified page(s) not listed")
    stale = sum(1 for s in claimed if s not in present)
    print(
        f"SUMMARY: type={type_name}, pages={len(present)}, unclassified={len(unclassified)}, "
        f"stale={stale}, errors=0"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Report on .wikicommit/groups/ group files.")
    parser.add_argument("--type", default=None, metavar="TYPE",
                        help="Report one Type in detail (e.g. DefinedTerm, custom/Decision)")
    parser.add_argument("--limit", type=int, default=0, metavar="N",
                        help="With --type: list at most N unclassified pages (0: all)")
    args = parser.parse_args()
    pages = pages_by_type(ENTITY_DIR, load_primary_lang(Path(".")))
    if args.type:
        return report_type(args.type.removeprefix("schema:"), pages, args.limit)
    return report_all(pages)


if __name__ == "__main__":
    sys.exit(main())
