#!/usr/bin/env python3
"""Detect `properties:` keys in a type schema file whose Schema.org
`rangeIncludes` includes a linkable entity type (Issue #496 — "entity-only"
or "mixed" range, per check_schema_org_type.py's --show-range classification)
but that the schema file gives no textual reinforcement toward writing as a
`[[Type/slug]]` WikiLink (docs/DesignDoc-data.md §4.1's property-value
WikiLink guidance).

Issue #523 found and fixed one such gap by hand (`publisher` on
BlogPosting.md/NewsArticle.md carried the same entity-only range as `author`,
which was reinforced, but had no reinforcement of its own) and then, via
`/code-review --fix` on that Issue's PR, found four more of the same shape
across other standard type templates (Organization.md's foundingLocation,
Person.md's affiliation, Place.md's containedInPlace, Event.md's
organizer/performer) by repeating the same manual `--show-range` cross-check.
This script automates that cross-check so the next such gap doesn't require
another manual audit to surface (Issue #539).

"Reinforcement" means either of the two forms Issue #523's fixes used:
  - the property name appears (as a whole word) in the schema file's
    `wikicommit.granularity` prose, e.g. Person.md's granularity entry
    mentioning "affiliation"; or
  - the `properties:` block's placeholder value for that key already
    contains a `[[...]]` WikiLink token (e.g. `affiliation: "[[Organization/slug]]"`),
    whether the value is a bare string or a list of strings.

A property with neither is reported as UNREINFORCED — not blocking (the
uniform Pass 3 rule in wikicommit-generate/SKILL.md already covers
unreinforced properties correctly in principle; this is only a nudge toward
the belt-and-suspenders reinforcement Issue #523 established as the norm for
this codebase's own type templates), and purely a starting point for human
judgment: a property may be deliberately left unreinforced if its dominant
real-world usage in this wiki's content is scalar rather than a link.

Only Schema.org-backed types are in scope. Custom types (`schema:custom/...`)
have no Schema.org vocabulary entry to classify a range against
(docs/DesignDoc-data.md §5.3), and `default.md` carries no `type:` at all —
both are silently skipped, the same exclusions check_schema_coverage.py
already applies for the same reason.

Usage:
    python .wikicommit/scripts/check_property_wikilink_reinforcement.py

Exit code: always 0 (informational, non-blocking, matching
check_schema_coverage.py/check_wanted_pages.py/etc.).
"""

import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_or_warn
from _schemaorg_vocab import entity_range_candidates, load_or_build_index, strip_prefix

SCHEMA_DIR = Path(".wikicommit/schema")


def collect_type_schema_files() -> list[Path]:
    if not SCHEMA_DIR.exists():
        return []
    return sorted(SCHEMA_DIR.rglob("*.md"))


def is_reinforced(prop_name: str, prop_value: object, granularity: list) -> bool:
    """True if prop_name is reinforced via granularity prose (Issue #523's
    "author lists multiple names; link each author..." pattern) or via a
    `[[...]]` WikiLink placeholder already present in the `properties:`
    value (Issue #523's "affiliation: [[Organization/slug]]" pattern) —
    either is sufficient, matching the two independent fixes Issue #523
    actually applied across different templates."""
    word = re.compile(rf"\b{re.escape(prop_name)}\b")
    if any(isinstance(g, str) and word.search(g) for g in granularity):
        return True

    values = prop_value if isinstance(prop_value, list) else [prop_value]
    return any(isinstance(v, str) and "[[" in v for v in values)


def check_file(path: Path, types: dict, properties: dict) -> list[tuple[str, str, list[str]]]:
    """Return a list of (type_name, prop_name, entity_candidates) for every
    unreinforced entity-linkable property in this schema file."""
    fm = parse_frontmatter_or_warn(path)
    if not fm:
        return []

    type_value = fm.get("type")
    if not isinstance(type_value, str) or not type_value.startswith("schema:"):
        return []
    type_name = strip_prefix(type_value)
    if type_name.startswith("custom/"):
        return []

    props = fm.get("properties")
    if not isinstance(props, dict):
        return []

    wikicommit_block = fm.get("wikicommit")
    granularity = wikicommit_block.get("granularity", []) if isinstance(wikicommit_block, dict) else []
    if not isinstance(granularity, list):
        granularity = []

    findings = []
    for prop_name, prop_value in props.items():
        result = entity_range_candidates(prop_name, properties, types)
        if result is None:
            continue  # not in the vocabulary at all — validate_frontmatter.py's concern
        entity_types, _datatype_types = result
        if not entity_types:
            continue  # DataType-only (or no rangeIncludes declared) — nothing to reinforce
        if not is_reinforced(prop_name, prop_value, granularity):
            findings.append((type_name, prop_name, entity_types))

    return findings


def main() -> int:
    index, err = load_or_build_index()
    if index is None:
        print(f"WARNING: Schema.org 語彙の取得に失敗したため、このチェックをスキップします: {err}")
        print("SUMMARY: unreinforced=0")
        return 0

    types = index["types"]
    properties = index["properties"]

    total = 0
    for path in collect_type_schema_files():
        for type_name, prop_name, entity_types in check_file(path, types, properties):
            total += 1
            print(
                f"UNREINFORCED: {type_name}.{prop_name} ({path}) — "
                f"range includes linkable entity type(s): {', '.join(entity_types)}. "
                "No granularity mention and no [[Type/slug]] placeholder in properties:."
            )

    print(f"SUMMARY: unreinforced={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
