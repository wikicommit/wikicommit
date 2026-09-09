#!/usr/bin/env python3
"""Verify that a Schema.org type (and optionally its properties) exist in the
official Schema.org vocabulary, or list every type name + one-line
description for preloading into an LLM's context.

Deterministic counterpart to the LLM judgment in wikicommit-generate's
`better_type_candidate` / `better_type_rationale` (Pass 2) and
wikicommit-schema-propose (Issue #285): this script can only confirm that a
type/property *exists* and that a property really belongs to the given type
(including its ancestor types). Whether the type is actually the *right*
semantic fit for a Wiki's content is a judgment left to the LLM and to human
PR review — this script does not attempt it.

Usage:
    python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> [--property <PropertyName>]... [--show-range]
    python .wikicommit/scripts/check_schema_org_type.py --type <TypeName> --list-properties
    python .wikicommit/scripts/check_schema_org_type.py --list-type-names
    python .wikicommit/scripts/check_schema_org_type.py --describe <TypeName>...
    python .wikicommit/scripts/check_schema_org_type.py --list-installed-hierarchy

`--list-type-names` and `--describe` are the two halves of type recall
(Issue #798). The three Skills that propose a type (wikicommit-init's
theme-driven step, wikicommit-collect's Type Proposal, wikicommit-generate
Pass 2b) each hold a short piece of text and need the vocabulary to jog a
candidate loose from it. That is *recall*, not verification — whether a type
actually exists is settled afterwards by `--type`, deterministically.

Recall does not need every description. `--list-type-names` prints the 933
type names alone (13 KB); the Skill picks a handful of candidates from them
and calls `--describe Park Museum ...` for just those descriptions (under a
kilobyte). Together that is ~14 KB against the 147 KB the old `--list-types`
put into the main context on every run, unconditionally and regardless of how
many sources were being processed.

`--list-types` (name + description for all 933) **was removed**, not kept
alongside. Once the three Skills moved to the two-stage form it had no caller,
and shipping the expensive path while documenting that nothing should use it
is the receptacle-without-a-consumer shape this project keeps out (Issue #553).
`--describe` covers the same need on demand.

`--describe` errors on a name that is not in the vocabulary rather than
silently omitting it: stage one hands the model 933 real names, so a name that
does not come back is an invention, and it is better caught here than carried
into the approval step.

`--list-installed-hierarchy` (Issue #565) prints one line per Schema.org type
installed in `.wikicommit/schema/`, tab-separated: the type, then its
*installed* ancestor types nearest-first (or `-`) — this is what
wikicommit-generate Pass 2c uses to prefer the most specific installed type,
since an ancestor type always fits and would otherwise win by familiarity.
Like `--list-type-names` it takes no other arguments and ignores them if given.

`--show-range` (Issue #496) adds one `RANGE:` line per verified `--property`,
reporting whether that property's Schema.org `rangeIncludes` points at
linkable entity type(s) (e.g. `affiliation` -> `Organization`), plain
DataType scalar(s) (e.g. `description` -> `Text`/`TextObject`), or a mix of
both (e.g. `jobTitle` -> `DefinedTerm` and `Text`) — this is what
wikicommit-generate Pass 2c/Pass 3 uses to decide whether a `properties:`
value should be written as a `[[Type/slug]]` WikiLink instead of a plain
scalar. Purely informational: `RANGE:` lines never affect the exit code or
`errors` count, and are only printed for a property that already verified OK
(a property that failed --property verification has no range worth reporting).

`--type <TypeName> --list-properties` (Issue #497) prints every property
available to that type — its own `domainIncludes` plus everything inherited
via its `rdfs:subClassOf` ancestry — one per line, tab-separated: property
name, declaring type(s) (which ancestor's domainIncludes it comes from),
entity-type WikiLink candidates from `rangeIncludes` (or `-` if none), and a
one-line description. This is the on-demand, per-type equivalent of
`--list-type-names`: a reference for picking what to put in a new (or existing)
type's `properties:` block, without pre-generating and maintaining a static
per-type template file (rejected design, see the Issue's background — that
would double-manage the same data schemaorg-vocab.json already holds and
defeats the schema layer's whole point of narrowing the field, not listing
everything). Takes priority over `--property`/`--show-range` when both
`--type` and `--list-properties` are given; `--list-type-names`, `--describe`
and then `--list-installed-hierarchy` take priority over everything if given
alongside `--type`.

Vocabulary loading/caching (.wikicommit/schemaorg-vocab.json) and the
domainIncludes/rangeIncludes/rdfs:subClassOf ancestry logic live in the
shared _schemaorg_vocab.py module (Issue #495, extended by Issues #496/#497),
also used by validate_frontmatter.py's `properties:` field validation.

Exit code: 0 = the type (and every given property) exists and, for
properties, belongs to the type or one of its ancestor types; or
--list-type-names/--describe/--list-installed-hierarchy/--list-properties
completed. 1 = the type does not exist, a property does not exist or does not
belong to the type lineage, a --describe name is not in the vocabulary, the
vocabulary could not be fetched/parsed, --list-properties was given without
--type, or none of --type/--list-type-names/--describe/
--list-installed-hierarchy was given.
"""

import argparse
import sys

from _schemaorg_vocab import (
    ancestors,
    entity_range_candidates,
    installed_standard_types,
    load_or_build_index,
    properties_available_to,
    property_in_domain,
    strip_prefix,
)


def _list_type_names(types: dict[str, dict]) -> int:
    """Print type names only — stage one of type recall (Issue #798).

    The three Skills that propose a type were each handed all 933 names *and*
    their descriptions, 147 KB, on every run. What that list actually did was
    jog a candidate loose from a short piece of text; it never established that
    a type exists, since `--type` settles that separately and deterministically
    after a candidate is approved. Recall does not need the descriptions of the
    928 types nobody is considering, so they moved behind `--describe`.
    """
    for name in sorted(types):
        print(name)
    print(f"SUMMARY: types={len(types)}")
    return 0


def _describe_types(names: list[str], types: dict[str, dict]) -> int:
    """Print name + one-line description for the named types — stage two (Issue #798).

    An unknown name is an ERROR rather than a silent omission. Stage one handed
    the model 933 real names, so a name that does not come back from it is an
    invention, and catching it here keeps it out of the approval step.
    """
    errors = 0
    for raw in names:
        name = strip_prefix(raw)
        entry = types.get(name)
        if entry is None:
            print(f"ERROR: schema:{name} does not exist in the Schema.org vocabulary")
            errors += 1
            continue
        print(f"{name}\t{entry.get('comment', '').strip()}")
    print(f"SUMMARY: described={len(names) - errors}, errors={errors}")
    return 1 if errors else 0


def _list_installed_hierarchy(types: dict[str, dict]) -> int:
    """Print the subClassOf relations that hold *among the installed types* (Issue #565).

    wikicommit-generate Pass 2c is handed the installed type list and each type's
    granularity, and nothing in that tells it `Park` is a kind of `Place`. Writing a
    park as a `Place` is not wrong — an ancestor type always fits — so the coarser,
    more familiar type wins by default and the installed `Park.md` goes unused
    (`wikicommit/saitama-city-wiki` generated seven parks as `Place` with `Park.md`
    installed in the same batch). This relation is derivable from the vocabulary, so
    it is computed here rather than left to the model to recall.

    One line per installed type, tab-separated: the type, then its installed
    ancestors (nearest first) or `-`. Types with no installed ancestor are listed
    too, so the output doubles as the installed-type roster.
    """
    installed = installed_standard_types()
    for name in sorted(installed):
        chain = [
            other for other in sorted(installed)
            if other != name and other in ancestors(name, types)
        ]
        # Nearest ancestor first: the deeper a type sits, the more specific it is.
        chain.sort(key=lambda other: len(ancestors(other, types)), reverse=True)
        print(f"{name}\t{', '.join(chain) if chain else '-'}")
    print(f"SUMMARY: installed_types={len(installed)}")
    return 0


def _entity_range_summary(prop_name: str, properties: dict, types: dict) -> str:
    """Compact single-field WikiLink-ability summary for --list-properties
    (Issue #497): the property's entity-type rangeIncludes candidates,
    comma-joined, or "-" if there are none (DataType-only, or no
    rangeIncludes declared at all). Deliberately terser than --show-range's
    full RANGE: sentence — this is one column in a scannable list, not a
    standalone message."""
    result = entity_range_candidates(prop_name, properties, types)
    if result is None:
        return "-"
    entity_types, _datatype_types = result
    return ", ".join(entity_types) if entity_types else "-"


def _list_properties(type_name: str, types: dict, properties: dict) -> int:
    available = properties_available_to(type_name, types, properties)
    for prop_name in sorted(available):
        declaring = ", ".join(available[prop_name])
        entity_range = _entity_range_summary(prop_name, properties, types)
        comment = properties[prop_name].get("comment", "").strip()
        print(f"{prop_name}\t{declaring}\t{entity_range}\t{comment}")
    print(f"SUMMARY: type=schema:{type_name}, properties={len(available)}")
    return 0


def _print_range(prop_name: str, properties: dict, types: dict) -> None:
    """Print one RANGE: line classifying prop_name's rangeIncludes as
    entity-only, DataType-only, or mixed (Issue #496). Silently no-ops if
    the property declares no rangeIncludes at all (rare, but not every
    Schema.org property has one) — there is nothing to report."""
    result = entity_range_candidates(prop_name, properties, types)
    if result is None:
        return
    entity_types, datatype_types = result
    if not entity_types and not datatype_types:
        return

    if entity_types and not datatype_types:
        print(
            f"RANGE: {prop_name} references entity types only (candidates: {', '.join(entity_types)}). "
            "Write the value as [[Type/slug]] when it names an entity that exists (or should exist) as its own page"
        )
    elif entity_types and datatype_types:
        print(
            f"RANGE: {prop_name} mixes entity types and data types "
            f"(entity candidates: {', '.join(entity_types)} / data type candidates: {', '.join(datatype_types)}). "
            "Write the value as [[Type/slug]] only when it names an entity that exists (or should exist) as its own page"
        )
    else:
        print(
            f"RANGE: {prop_name} references data types only (candidates: {', '.join(datatype_types)}). "
            "No WikiLink is needed"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Schema.org type/property exists in the official vocabulary.")
    parser.add_argument("--type", metavar="<TypeName>")
    parser.add_argument("--property", action="append", default=[], dest="properties", metavar="<PropertyName>")
    parser.add_argument(
        "--list-type-names", action="store_true",
        help="Print every Schema.org type name (no descriptions), then exit (Issue #798). "
        "Stage one of type recall; pair it with --describe for the candidates you pick. "
        "Ignores --type/--property.",
    )
    parser.add_argument(
        "--describe", nargs="+", default=None, metavar="<TypeName>",
        help="Print name and one-line description for the named types, then exit (Issue #798). "
        "Stage two of type recall. A name not in the vocabulary is an ERROR.",
    )
    parser.add_argument(
        "--list-installed-hierarchy", action="store_true",
        help="Print each Schema.org type installed in .wikicommit/schema/ with its "
        "installed ancestor types, then exit (Issue #565). Takes no other arguments.",
    )
    parser.add_argument(
        "--show-range", action="store_true",
        help="For each verified --property, also print a RANGE: line classifying its rangeIncludes "
        "as entity/DataType/mixed (Issue #496). Informational only — never affects the exit code.",
    )
    parser.add_argument(
        "--list-properties", action="store_true",
        help="With --type, list every property available to that type (own + inherited via "
        "rdfs:subClassOf ancestry), then exit (Issue #497). Requires --type; ignores --property/"
        "--show-range. Takes priority over the --property verification mode when both are given.",
    )
    args = parser.parse_args()

    index, err = load_or_build_index()
    if index is None:
        print(f"ERROR: the Schema.org vocabulary could not be loaded: {err}")
        return 1

    types = index["types"]
    properties = index["properties"]

    if args.list_type_names:
        return _list_type_names(types)

    if args.describe:
        return _describe_types(args.describe, types)

    if args.list_installed_hierarchy:
        return _list_installed_hierarchy(types)

    if not args.type:
        if args.list_properties:
            print("ERROR: --list-properties requires --type")
            return 1
        print("ERROR: specify one of --type / --list-type-names / --describe / --list-installed-hierarchy")
        return 1

    type_name = strip_prefix(args.type)

    if args.list_properties:
        if type_name not in types:
            print(f"ERROR: schema:{type_name} does not exist in the Schema.org vocabulary")
            return 1
        return _list_properties(type_name, types, properties)

    errors = 0
    checked = 0

    type_exists = type_name in types
    checked += 1
    if type_exists:
        print(f"OK: schema:{type_name} exists in the Schema.org vocabulary")
    else:
        print(f"ERROR: schema:{type_name} does not exist in the Schema.org vocabulary")
        errors += 1

    ancestry = ancestors(type_name, types) if type_exists else set()

    for prop in args.properties:
        prop_name = strip_prefix(prop)
        checked += 1

        if not type_exists:
            print(f"ERROR: schema:{type_name} does not exist, so the domain of {prop_name} cannot be verified")
            errors += 1
            continue

        in_domain = property_in_domain(prop_name, ancestry, properties)
        if in_domain is None:
            print(f"ERROR: {prop_name} does not exist in the Schema.org vocabulary")
            errors += 1
        elif in_domain:
            print(f"OK: {prop_name} belongs to schema:{type_name} (or one of its ancestor types)")
            if args.show_range:
                _print_range(prop_name, properties, types)
        else:
            print(f"ERROR: {prop_name} belongs to neither schema:{type_name} nor any of its ancestor types")
            errors += 1

    print(f"SUMMARY: type=schema:{type_name}, checked={checked}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
