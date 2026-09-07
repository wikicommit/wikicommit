#!/usr/bin/env python3
"""Detect tags that only repeat a page's own title or type (Issue #571).

`tags` exists to group pages across the wiki by something they share — a field,
a technique, a period. A tag equal to the page's own title carries none of that:
it groups the page with itself. Neither does one equal to the page's `type`,
which the `type:` field already says. Both were ruled out in prose when `tags`
was defined (Issue #275), and both came back: a pilot shipped
`Place/minuma-tanbo.md` tagged `見沼田んぼ` and `Place/saitama-shintoshin.md`
tagged `さいたま新都心`, plus five pages tagged with their own category.

A generation-time rule with nothing checking it is a rule that drifts. This is
the same "automate the one-off manual audit" role
check_property_wikilink_reinforcement.py (Issue #539) plays for type templates.

Matching is **exact after normalization** — NFKC, case-folded, whitespace
collapsed — and never partial. A tag that merely contains part of the title is
usually the useful kind: `見沼` on a page titled `見沼田んぼ` groups it with
everything else in that area, which is exactly what tags are for. Reporting it
would train people to ignore this check.

Known limitation: a type tag written in the wiki's own language is not caught.
`博物館` on a `schema:Museum` page duplicates the type as surely as `museum`
would, but seeing that needs a translation of the Schema.org vocabulary, which
WikiCommit does not have and deliberately does not keep (type names are
language-neutral identifiers). English-language wikis are covered; others get
the title half only.

Usage:
    python .wikicommit/scripts/check_self_referential_tags.py

Exit code: always 0 (warning-only, non-blocking).
"""

import re
import sys
import unicodedata

from _frontmatter import parse_frontmatter
from _wikilink import ENTITY_DIR, collect_entity_pages, normalize_name, parse_wiki_path


# A lowercase (or digit) followed by an uppercase letter — the boundary inside
# `GovernmentService`. Kept narrow on purpose: acronym runs such as `HTMLPage`
# are left whole rather than guessed at.
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _split_words(value: str) -> list[str]:
    """Words of a label, so the spellings of one type name compare equal.

    `GovernmentService`, `government-service` and `government service` are the
    same type written three ways; splitting on case boundaries as well as on
    hyphens, underscores and whitespace makes them all `["government",
    "service"]`. Scripts with no case distinction are unaffected — the case
    boundary simply never occurs.
    """
    spaced = _CAMEL_BOUNDARY.sub(" ", unicodedata.normalize("NFKC", value))
    return [w for w in spaced.replace("-", " ").replace("_", " ").casefold().split() if w]


def type_labels(type_value: object, type_name: str) -> set[str]:
    """The forms of a page's type a tag could be repeating.

    Both the last segment of the type name (`Decision` for `custom/Decision`)
    and the whole thing, so `custom/Decision` is caught alongside `Decision`.
    """
    raw = {type_name, type_name.rsplit("/", 1)[-1]}
    if isinstance(type_value, str) and type_value:
        raw.add(type_value)
    labels = set()
    for label in raw:
        if not label:
            continue
        labels.add(normalize_name(label))
        # Word-split form too, so `government-service` matches `GovernmentService`.
        # Derived from the raw label — normalize_name() lowercases, which would
        # erase the case boundary the split relies on.
        labels.add(" ".join(_split_words(label)))
    return {label for label in labels if label}


def main() -> int:
    if not ENTITY_DIR.exists():
        print("SUMMARY: title_echo=0, type_echo=0")
        return 0

    title_echo = 0
    type_echo = 0
    pages = collect_entity_pages(ENTITY_DIR)

    for page in pages:
        frontmatter, error = parse_frontmatter(page)
        if frontmatter is None:
            print(f"WARNING: {page}: {error}", file=sys.stderr)
            continue
        if frontmatter.get("status") == "removed":
            continue
        tags = frontmatter.get("tags")
        if not isinstance(tags, list):
            continue

        resolved = parse_wiki_path(page, ENTITY_DIR)
        type_name = resolved[1] if resolved else ""
        labels = type_labels(frontmatter.get("type"), type_name)

        title = frontmatter.get("title")
        title_key = normalize_name(title) if isinstance(title, str) else ""

        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                continue
            key = normalize_name(tag)
            spaced = " ".join(_split_words(tag))
            if title_key and key == title_key:
                print(
                    f'TITLE_ECHO: {page}: tag "{tag}" repeats the page title'
                    f" (it can only group the page with itself)"
                )
                print(f"page: {page}")
                title_echo += 1
            elif key in labels or spaced in labels:
                print(
                    f'TYPE_ECHO: {page}: tag "{tag}" repeats the page type'
                    f" (the type: field already says this)"
                )
                print(f"page: {page}")
                type_echo += 1

    print(f"SUMMARY: title_echo={title_echo}, type_echo={type_echo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
