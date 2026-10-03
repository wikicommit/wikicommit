#!/usr/bin/env python3
"""check_name_collisions.py — pages that answer to the same name (Issue #1095).

A concept that two sources call by different names gets two pages, because
generation matches an existing page by Type and slug (and, since Issue #1096,
by title and aliases at the moment of writing). What is left over shows up as
a name collision: one page's title or alias is another page's title or alias.

This script lists those collisions — `/wikicommit-status` counts them and
`/wikicommit-relate` puts each to a person — same concept, one inside the other, related,
distinct, or editions of one series. It is also
the first reader of `.wikicommit/relations.yml`: a pair a person has already
decided about, in any relation, is not raised again. Without that reader a
"these are distinct" decision would have nowhere to take effect, and the same
pair would come back on every run.

Comparison is per language directory (titles and aliases are written in one
language), on `normalize_name()` — NFKC, case-folded, whitespace collapsed —
and nothing else. Two names that merely mean the same thing are not matched.
A title-against-title clash between two pages of the same Type is left to
`check_orphans.py`, which reports it as a blocking `DUPLICATE:`.

    COLLISION: "<name>" (<lang>) — <Type/slug> (title), <Type/slug> (alias)
    SUMMARY: collisions=<N>, judged_pairs_skipped=<N>, relations=<N>

`index.md` and `status: removed` pages are skipped. A relations file that
cannot be read gives a WARNING on stderr and counts as no decisions.

Exit code: 0 always (a report, never a gate).
"""

import itertools
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter
from _wikilink import ENTITY_DIR, collect_entity_pages, normalize_name, parse_wiki_path

RELATIONS_FILE = Path(".wikicommit/relations.yml")


def load_judged_pairs(relations_file: Path = RELATIONS_FILE) -> tuple[set[frozenset], int]:
    """Every pair of pages named together in one item of the relations file.

    Returns (pairs, number of items read). A file that cannot be read gives a
    WARNING and counts as no decisions — the collisions are then all raised,
    which is the side to err on. An item without a `pages` list is skipped
    with a WARNING.
    """
    judged: set[frozenset] = set()
    if not relations_file.is_file():
        return judged, 0
    try:
        data = yaml.safe_load(relations_file.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"WARNING: {relations_file.as_posix()} could not be read, ignored: {exc}", file=sys.stderr)
        return judged, 0
    if data is None:
        return judged, 0
    if not isinstance(data, list):
        print(f"WARNING: {relations_file.as_posix()} is not a YAML list, ignored", file=sys.stderr)
        return judged, 0
    items = 0
    for n, record in enumerate(data):
        if not isinstance(record, dict) or not isinstance(record.get("pages"), list):
            print(f"WARNING: {relations_file.as_posix()} item {n} has no `pages` list, ignored", file=sys.stderr)
            continue
        items += 1
        members = {p for p in record["pages"] if isinstance(p, str)}
        if isinstance(record.get("broader"), str):
            members.add(record["broader"])
        for a, b in itertools.combinations(sorted(members), 2):
            judged.add(frozenset((a, b)))
    return judged, items


def collect_names(entity_dir: Path = ENTITY_DIR) -> dict[tuple[str, str], list[tuple[str, str, str, str]]]:
    """(lang, normalized name) -> [(Type/slug, Type, kind, name as written)]."""
    names: dict[tuple[str, str], list[tuple[str, str, str, str]]] = {}
    for page in collect_entity_pages(entity_dir):
        parsed = parse_wiki_path(page, entity_dir)
        if parsed is None:
            continue
        lang, type_name, slug = parsed
        fm, _ = parse_frontmatter(page)
        if not isinstance(fm, dict) or fm.get("status") == "removed":
            continue
        ident = f"{type_name}/{slug}"
        entries = []
        if isinstance(fm.get("title"), str) and fm["title"].strip():
            entries.append(("title", fm["title"]))
        if isinstance(fm.get("aliases"), list):
            entries.extend(("alias", a) for a in fm["aliases"] if isinstance(a, str) and a.strip())
        seen = set()
        for kind, name in entries:
            key = (lang, normalize_name(name))
            if key in seen:
                continue
            seen.add(key)
            names.setdefault(key, []).append((ident, type_name, kind, name.strip()))
    return names


def main() -> int:
    judged, items = load_judged_pairs()
    collisions = skipped = 0
    for (lang, _key), holders in sorted(collect_names().items()):
        name = holders[0][3]
        by_page = {}
        for ident, type_name, kind, _written in holders:
            by_page.setdefault(ident, (type_name, kind))
        if len(by_page) < 2:
            continue
        open_pairs = []
        for a, b in itertools.combinations(sorted(by_page), 2):
            (ta, ka), (tb, kb) = by_page[a], by_page[b]
            if ka == "title" and kb == "title" and ta == tb:
                continue  # check_orphans.py reports this as DUPLICATE:
            if frozenset((a, b)) in judged:
                skipped += 1
                continue
            open_pairs.append((a, b))
        if not open_pairs:
            continue
        involved = sorted({p for pair in open_pairs for p in pair})
        listed = ", ".join(f"{p} ({by_page[p][1]})" for p in involved)
        print(f'COLLISION: "{name}" ({lang}) — {listed}')
        collisions += 1
    print(f"SUMMARY: collisions={collisions}, judged_pairs_skipped={skipped}, relations={items}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
