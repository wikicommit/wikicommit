#!/usr/bin/env python3
"""Detect `properties:` values naming a page that exists, written as plain text (Issue #561).

Pass 3 decides whether to write a `properties:` value as `[[Type/slug]]` from
the property's Schema.org range alone (Issue #496), and its instructions say in
so many words not to let a missing target page stop it. `wikicommit/decameron-wiki`
did exactly that anyway: `Book/decameron.md` lists ten narrators under
`character`, and the eight whose Person pages had already been written by the
same ingest are WikiLinks while the two written by a *later* ingest are bare
strings. Same property, same value list, same type — the split is the order the
sources happened to be ingested in, nothing about the people.

Nothing self-corrects afterwards. `action: update` reaches a page only when a
source for *that page* is re-ingested, so the later ingest that finally created
`Person/filostrato` had no reason to revisit the Book page still spelling the
name out.

Nor does anything report it. The existing checks cover the mirror image:

  check_wanted_pages.py   a link with no page behind it
  this script             a page with no link in front of it

check_wikilinks.py reads only WikiLinks that were written, and check_orphans.py
misses it whenever the page has backlinks from somewhere else — which
`Person/filostrato` did, from the tale pages. So `/wikicommit-status` went on
reporting a clean wiki.

Scope is `properties:` values, never body prose. Issue #318's limitation stands
for free text, but a `properties:` value is by definition short and structured
(Issue #495), which is what makes matching it against page titles worth doing.

A match must agree on type as well as name: the page found has to be one of the
property's own `rangeIncludes` entity candidates, or a subtype of one, so
`genre: "Comedy"` cannot be answered by a `Person/comedy` page.

Known limitations, both deliberate:
  - Two unrelated subjects sharing a name read as one. Warning-only output,
    same tolerance check_wanted_pages.py documents for its own limits.
  - A custom-typed page (`schema:custom/...`) cannot be a *target*: it has no
    Schema.org entry, so there is no way to tell whether it satisfies a
    property's range. It is still scanned as a *referrer* — the range
    classification is keyed on the property name alone and never consults the
    referring page's own type, so a `custom/Tale` listing a `character` is
    judged exactly as a `ShortStory` would be. (validate_frontmatter.py and
    check_property_wikilink_reinforcement.py skip custom types outright, but
    both validate a key against its *owning type's* domainIncludes, which is
    the part that has no answer here.) A custom type's `properties:` keys are
    not machine-validated, so an invented key simply misses the vocabulary and
    is skipped like any other unknown property.

Usage:
    python .wikicommit/scripts/check_unlinked_entity_mentions.py

Exit code: always 0 (warning-only, non-blocking).
"""

import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _schemaorg_vocab import ancestors, entity_range_candidates, load_or_build_index
from _wikilink import (
    ENTITY_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    normalize_name,
    parse_wiki_path,
)


def collect_pages() -> list[Path]:
    return collect_entity_pages(ENTITY_DIR)


def page_names(frontmatter: dict, slug: str) -> list[str]:
    """Every name this page answers to — `title`, each `aliases` entry, and its slug.

    A value is written in the wiki's own language while the slug is a
    language-neutral English identifier (Issue #193), so the two rarely coincide
    — but they do for English-language wikis, and `aliases` is the field already
    reserved for the alternate spellings a value may use instead of the title.
    """
    names = [slug]
    title = frontmatter.get("title")
    if isinstance(title, str) and title.strip():
        names.append(title.strip())
    aliases = frontmatter.get("aliases")
    if isinstance(aliases, list):
        names.extend(a.strip() for a in aliases if isinstance(a, str) and a.strip())
    return names


def plain_string_values(raw: object) -> list[str]:
    """The plain-text strings among a property's value(s).

    A value holding a WikiLink is already what the rule asks for; a value that
    merely embeds one is left alone too, rather than reported on the strength of
    the surrounding text.
    """
    items = raw if isinstance(raw, list) else [raw]
    return [
        item.strip()
        for item in items
        if isinstance(item, str) and item.strip() and not WIKILINK_RE.search(item)
    ]


def main() -> int:
    index, err = load_or_build_index()
    if index is None:
        print(f"WARNING: the Schema.org vocabulary could not be loaded, so this check was skipped: {err}")
        print("SUMMARY: unlinked=0")
        return 0
    types, properties = index["types"], index["properties"]

    pages = collect_pages()

    # normalized name -> {(type_name, slug)}; every page is a possible target,
    # the property's range decides which of them may answer a given value.
    name_index: dict[str, set[tuple[str, str]]] = {}
    # path -> (frontmatter, type_name, slug), so the scan below re-reads nothing.
    parsed: dict[Path, tuple[dict, str, str]] = {}

    for page in pages:
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
        parsed[page] = (frontmatter, type_name, slug)
        for name in page_names(frontmatter, slug):
            name_index.setdefault(normalize_name(name), set()).add((type_name, slug))

    # property name -> the entity types a value of it may link to, or an empty
    # set for "never a WikiLink here" (DataType-only range, no rangeIncludes at
    # all, or not in the vocabulary). Depends on the property name alone, so it
    # is resolved once rather than per page that happens to declare it.
    linkable_range: dict[str, set[str]] = {}

    def allowed_target_types(prop_name: str) -> set[str]:
        if prop_name not in linkable_range:
            result = entity_range_candidates(prop_name, properties, types)
            # result is None: not in the vocabulary at all — validate_frontmatter.py's
            # concern, not this script's.
            linkable_range[prop_name] = set(result[0]) if result else set()
        return linkable_range[prop_name]

    total = 0
    for page, (frontmatter, page_type, page_slug) in parsed.items():
        props = frontmatter.get("properties")
        if not isinstance(props, dict):
            continue

        for prop_name, raw in props.items():
            allowed = allowed_target_types(prop_name)
            if not allowed:
                continue

            for value in plain_string_values(raw):
                targets = name_index.get(normalize_name(value))
                if not targets:
                    continue
                matches = sorted(
                    f"{target_type}/{target_slug}"
                    for target_type, target_slug in targets
                    if (target_type, target_slug) != (page_type, page_slug)
                    and not target_type.startswith("custom/")
                    and allowed & ancestors(target_type, types)
                )
                if not matches:
                    continue
                total += 1
                print(
                    f"UNLINKED: {page}: properties.{prop_name} \"{value}\" exists as"
                    f" {', '.join(matches)} but is not written as a WikiLink"
                )
                print(f"page: {page}")

    print(f"SUMMARY: unlinked={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
