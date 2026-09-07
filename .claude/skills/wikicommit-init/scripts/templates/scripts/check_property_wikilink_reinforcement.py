#!/usr/bin/env python3
"""Detect `properties:` keys in a type schema file whose Schema.org
`rangeIncludes` includes a linkable entity type (Issue #496 — "entity-only"
or "mixed" range, per check_schema_org_type.py's --show-range classification)
but that the schema file gives no textual reinforcement toward writing as a
`[[Type/slug]]` WikiLink.

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
  - the schema file's `wikicommit.granularity` prose has a bullet that names
    the property (as a whole word) *and* points toward linking it — the rest of
    the bullet contains `[[` or the substring `link` (Issue #650; see
    LINK_CUE_RE below for why naming it alone is not enough), e.g.
    BlogPosting.md's granularity entry "author lists multiple names; link each
    author ... with a WikiLink"; or
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
have no Schema.org vocabulary entry to classify a range against, and
`default.md` carries no `type:` at all —
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


def granularity_strings(path: Path, wikicommit_block: object) -> list[str]:
    """Return the `wikicommit.granularity` bullets that are usable as prose,
    warning about every entry that is not (Issue #649).

    An unquoted YAML list item containing a top-level `key: value` shape is
    parsed as a single-key mapping, not as a scalar — so a bullet written as
    `Boundary with NewsArticle: a BlogPosting is ...` reaches this script as a
    dict. Dropping those silently makes the reinforcement search miss prose
    that is plainly there, and the resulting UNREINFORCED line then reads as a
    human oversight (the template does mention the property) rather than as a
    parse artifact. The bullets this repository distributes are held to the
    string form by tests/test_schema_template_boundary_rules.py, but type files
    written at runtime by wikicommit-generate Pass 2b / wikicommit-schema-propose,
    or by hand (`provenance: manual`), are outside that test's reach.

    The entry is still skipped rather than reconstructed from the mapping: a
    colon-bearing bullet is a latent trap for any consumer that reads
    `granularity`, so the fix belongs in the schema file, and reconstructing it
    here would hide the very shape that needs fixing.
    """
    granularity = wikicommit_block.get("granularity", []) if isinstance(wikicommit_block, dict) else []
    if not isinstance(granularity, list):
        print(
            f"WARNING: {path}: wikicommit.granularity is not a list "
            f"({type(granularity).__name__}), so this type's granularity is excluded from the check"
        )
        return []

    usable = []
    for i, entry in enumerate(granularity):
        if isinstance(entry, str):
            usable.append(entry)
            continue
        print(
            f"WARNING: {path}: wikicommit.granularity[{i}] parsed as "
            f"{type(entry).__name__} rather than a string (a colon inside the bullet was "
            "probably read as a YAML mapping). That bullet is excluded from the check, so a "
            "property reinforced there can be reported as UNREINFORCED. "
            "Replace the colon separator with an em dash (—)"
        )
    return usable


# A granularity bullet counts as prose reinforcement only if it also points
# toward linking (Issue #650). Naming the property alone is not enough: a bullet
# can name one in order to say the opposite, and mentioning-only matching read
# those as reinforcement twice in a row — HowTo.md's boundary rule ending in
# "the service, tool, or concept they operate on" silenced HowTo.tool (Issue
# #550), and then a bullet added to say `tool`/`supply` are often empty and
# should be left out silenced both tool and supply (Issue #551). The first was
# fixed by rewording; the second could not be, because naming those two
# properties is that bullet's entire purpose.
#
# Every reinforcement Issue #523 actually wrote satisfies this ("link each
# author who independently qualifies for their own [[Person/slug]] page with a
# WikiLink"), and both negative bullets above fail it. `link` is matched as a
# substring so that "WikiLink", "linked" and "linking" all count.
#
# The cue is looked for in the bullet with the property's own name removed, so
# that a property whose *name* contains the substring (schema:originalMediaLink,
# whose range includes MediaObject/WebPage and so is in scope here) cannot
# satisfy the cue by being named — for those, naming alone would otherwise still
# be enough and this whole requirement would be a no-op.
#
# This narrows the false-positive class rather than closing it: a bullet that
# says not to link a property ("do not link `tool` values") still reads as
# reinforcement, since no regex settles polarity. The failure direction is the
# safe one — a positive reinforcement worded without either cue is reported as
# UNREINFORCED, which is a non-blocking nudge to look at, not a broken build.
LINK_CUE_RE = re.compile(r"\[\[|link", re.IGNORECASE)


def is_reinforced(prop_name: str, prop_value: object, granularity: list[str]) -> bool:
    """True if prop_name is reinforced via granularity prose (Issue #523's
    "author lists multiple names; link each author..." pattern — the bullet has
    to name the property *and*, elsewhere in that same bullet, point toward
    linking, per LINK_CUE_RE above) or
    via a `[[...]]` WikiLink placeholder already present in the `properties:`
    value (Issue #523's "affiliation: [[Organization/slug]]" pattern) —
    either is sufficient, matching the two independent fixes Issue #523
    actually applied across different templates."""
    word = re.compile(rf"\b{re.escape(prop_name)}\b")
    if any(word.search(g) and LINK_CUE_RE.search(word.sub(" ", g)) for g in granularity):
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

    granularity = granularity_strings(path, fm.get("wikicommit"))

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
        print(f"WARNING: the Schema.org vocabulary could not be loaded, so this check was skipped: {err}")
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
                "No granularity line points toward linking it, and no [[Type/slug]] "
                "placeholder in properties:."
            )

    print(f"SUMMARY: unreinforced={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
