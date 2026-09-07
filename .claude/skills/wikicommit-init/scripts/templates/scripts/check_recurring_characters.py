#!/usr/bin/env python3
"""Detect named characters listed as plain text in properties.character (Issue #560).

`ShortStory.md` / `Book.md` tell Pass 3 to WikiLink a character who qualifies for
a `[[Person/slug]]` page of their own and to list the rest as plain text. Nothing
ever revisits that call. A character the wiki never promoted stays a bare string
in every work that features them, and no existing check sees it:
check_wanted_pages.py only reads `[[Type/slug]]` WikiLinks, so a plain-text name
is not even counted as wanted (the Issue #318 limitation, applied to
`properties:` values), and check_orphans.py is about backlinks to pages that do
exist. `wikicommit/decameron-wiki` went on reporting a clean bill of health while
Calandrino — the lead of four separate tales — appeared as the plain string
"Calandrino" four times over and had no page at all.

One finding: RECURRING — the same name in two or more works, with no Person
page anywhere. Recurrence across works is the evidence a single work cannot
give: this person exists beyond any one plot. Promote them, or decide once that
they stay plain text.

A name that *does* already have a Person page is a different finding — nothing
needs writing, the value should simply be a WikiLink (Issue #496) — and belongs
to check_unlinked_entity_mentions.py, which reports it across every
entity-ranged `properties:` key rather than `character` alone (Issue #561).
Page existence is still read here, but only to keep such a name out of the
promotion list.

Works are counted by `<Type>/<slug>`, not by file, so the three language
versions of one story count once — otherwise every translated wiki would report
its whole cast as recurring.

Known limitations, all deliberate:
  - Only the promotion axis a wiki can see from the outside is covered. A
    protagonist who appears in exactly one work is invisible here no matter how
    thoroughly that work is about them; that call belongs to `Person.md`'s
    granularity at generation time, not to a cross-page tally.
  - Names are matched to pages by normalized title or alias, so two unrelated
    people sharing a name read as one. Warning-only output, same tolerance as
    check_wanted_pages.py's own documented limits.
  - Recurrence counts only the works that spell the name out. A work that
    already writes `[[Person/slug]]` for a character whose page nobody has
    written yet does not count toward the threshold, so one linked work plus one
    plain-text work reports nothing. Connecting the two would mean deriving a
    slug from a plain-text name, which the slug rules (English identifiers,
    translated or transliterated by kind — Issue #193) do not make reversible.
    The dangling link itself is check_wanted_pages.py's finding; once the Person
    page exists, the plain-text work surfaces in
    check_unlinked_entity_mentions.py.

Usage:
    python .wikicommit/scripts/check_recurring_characters.py

Exit code: always 0 (warning-only, non-blocking).
"""

import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import (
    ENTITY_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    normalize_name,
    parse_wiki_path,
)

# Frontmatter `properties:` keys whose values name people. Only `character` for
# now: it is the one key the distributed templates explicitly tell Pass 3 to
# leave as plain text when the person does not qualify for a page, which is what
# makes an unpromoted value indistinguishable from a deliberate one. Extend this
# tuple only for a key with that same "plain text is a legitimate outcome" shape.
PERSON_VALUED_PROPERTIES = ("character",)

PERSON_TYPE = "Person"

# Two works. One is just a cast list; the second is the earliest point at which
# the wiki itself is saying this person outlives any single work.
RECURRENCE_THRESHOLD = 2


def collect_pages() -> list[Path]:
    return collect_entity_pages(ENTITY_DIR)


def person_page_names(frontmatter: dict) -> list[str]:
    """Every name a Person page answers to — its `title` plus any `aliases`.

    Matching on `title` alone reports a character as RECURRING ("no Person page
    anywhere") whenever the page is filed under a fuller or otherwise different
    form of the name: `Person/ser-ciappelletto`, titled "Ser Ciappelletto",
    against works listing the plain string "Ciappelletto". Acting on that line
    writes a second page for a person who already has one — the same wrong move
    check_wanted_pages.py's TYPE_MISMATCH split exists to prevent (Issue #563),
    and one check_orphans.py's duplicate detection would not catch either, since
    the two pages differ in title. `aliases` is the frontmatter field already
    reserved for exactly these alternate spellings, so it answers the name too.
    """
    names = []
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        names.append(title.strip())
    aliases = frontmatter.get("aliases")
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                names.append(alias.strip())
    return names


def character_values(frontmatter: dict) -> list[str]:
    """Every plain-string value under the person-valued `properties:` keys.

    A value already written as a WikiLink is exactly what these rules ask for,
    so it is dropped here rather than reported.
    """
    properties = frontmatter.get("properties")
    if not isinstance(properties, dict):
        return []

    values = []
    for key in PERSON_VALUED_PROPERTIES:
        raw = properties.get(key)
        if raw is None:
            continue
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if not isinstance(item, str):
                continue
            name = item.strip()
            if not name or WIKILINK_RE.fullmatch(name):
                continue
            values.append(name)
    return values


def main() -> int:
    # normalized name -> {"<Type>/<slug>" of each work listing it as plain text}
    plain_text_works: dict[str, set[str]] = {}
    # normalized name -> the spelling to print (first one seen, path-sorted)
    display_name: dict[str, str] = {}
    # normalized names (title or alias) that a Person page answers to. Only
    # membership is read: a name with a page is check_unlinked_entity_mentions.py's
    # finding, so all this list does is keep it off the promotion list below.
    person_pages: set[str] = set()

    for page in collect_pages():
        frontmatter, error = parse_frontmatter(page)
        if frontmatter is None:
            print(f"WARNING: {page}: {error}", file=sys.stderr)
            continue
        if frontmatter.get("status") == "removed":
            continue

        resolved = parse_wiki_path(page, ENTITY_DIR)
        if resolved is None:
            continue
        _, type_name, slug = resolved

        if type_name == PERSON_TYPE:
            person_pages.update(
                normalize_name(page_name) for page_name in person_page_names(frontmatter)
            )

        work_key = f"{type_name}/{slug}"
        for name in character_values(frontmatter):
            key = normalize_name(name)
            plain_text_works.setdefault(key, set()).add(work_key)
            display_name.setdefault(key, name)

    recurring_count = 0
    for key in sorted(plain_text_works):
        if key in person_pages:
            continue  # has a page already — check_unlinked_entity_mentions.py's finding
        works = sorted(plain_text_works[key])
        if len(works) < RECURRENCE_THRESHOLD:
            continue
        print(
            f"RECURRING: \"{display_name[key]}\" appears as plain text in {len(works)} work(s) "
            f"but has no Person page ({', '.join(works)})"
        )
        recurring_count += 1

    print(f"SUMMARY: recurring={recurring_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
