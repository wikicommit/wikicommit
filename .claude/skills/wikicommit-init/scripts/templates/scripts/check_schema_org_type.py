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
    python .wikicommit/scripts/check_schema_org_type.py --list-types

`--list-types` prints every Schema.org type name and its one-line
description (tab-separated) — this is what wikicommit-generate Pass 2 uses
to preload the full vocabulary into the LLM's context (docs/DesignDoc-skills.md
§11.6), rather than a script trying to guess "the right type" itself.

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
`--list-types`: a reference for picking what to put in a new (or existing)
type's `properties:` block, without pre-generating and maintaining a static
per-type template file (rejected design, see the Issue's background — that
would double-manage the same data schemaorg-vocab.json already holds and
defeats the schema layer's whole point of narrowing the field, not listing
everything). Takes priority over `--property`/`--show-range` when both
`--type` and `--list-properties` are given; `--list-types` takes priority
over everything if given alongside `--type`.

Vocabulary loading/caching (.wikicommit/schemaorg-vocab.json) and the
domainIncludes/rangeIncludes/rdfs:subClassOf ancestry logic live in the
shared _schemaorg_vocab.py module (Issue #495, extended by Issues #496/#497),
also used by validate_frontmatter.py's `properties:` field validation.

Exit code: 0 = the type (and every given property) exists and, for
properties, belongs to the type or one of its ancestor types; or --list-types/
--list-properties completed. 1 = the type does not exist, a property does not
exist or does not belong to the type lineage, the vocabulary could not be
fetched/parsed, --list-properties was given without --type, or neither
--type nor --list-types was given.
"""

import argparse
import sys

from _schemaorg_vocab import (
    ancestors,
    entity_range_candidates,
    load_or_build_index,
    properties_available_to,
    property_in_domain,
    strip_prefix,
)


def _list_types(types: dict[str, dict]) -> int:
    for name in sorted(types):
        comment = types[name].get("comment", "").strip()
        print(f"{name}\t{comment}")
    print(f"SUMMARY: types={len(types)}")
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
            f"RANGE: {prop_name} はエンティティ型のみを参照します（候補: {', '.join(entity_types)}）。"
            "値が独立したページとして存在する（べき）エンティティを指す場合は [[Type/slug]] 形式で書いてください"
        )
    elif entity_types and datatype_types:
        print(
            f"RANGE: {prop_name} はエンティティ型とデータ型が混在します"
            f"（エンティティ候補: {', '.join(entity_types)} / データ型候補: {', '.join(datatype_types)}）。"
            "値が独立したページとして存在する（べき）エンティティを指す場合のみ [[Type/slug]] 形式で書いてください"
        )
    else:
        print(
            f"RANGE: {prop_name} はデータ型のみを参照します（候補: {', '.join(datatype_types)}）。"
            "WikiLink 化は不要です"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Schema.org type/property exists in the official vocabulary.")
    parser.add_argument("--type", metavar="<TypeName>")
    parser.add_argument("--property", action="append", default=[], dest="properties", metavar="<PropertyName>")
    parser.add_argument(
        "--list-types", action="store_true",
        help="Print every Schema.org type name and description, then exit (ignores --type/--property).",
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
        print(f"ERROR: Schema.org 語彙の取得に失敗しました: {err}")
        return 1

    types = index["types"]
    properties = index["properties"]

    if args.list_types:
        return _list_types(types)

    if not args.type:
        if args.list_properties:
            print("ERROR: --list-properties には --type の指定が必要です")
            return 1
        print("ERROR: --type または --list-types のいずれかを指定してください")
        return 1

    type_name = strip_prefix(args.type)

    if args.list_properties:
        if type_name not in types:
            print(f"ERROR: schema:{type_name} は Schema.org 語彙に存在しません")
            return 1
        return _list_properties(type_name, types, properties)

    errors = 0
    checked = 0

    type_exists = type_name in types
    checked += 1
    if type_exists:
        print(f"OK: schema:{type_name} は Schema.org 語彙に存在します")
    else:
        print(f"ERROR: schema:{type_name} は Schema.org 語彙に存在しません")
        errors += 1

    ancestry = ancestors(type_name, types) if type_exists else set()

    for prop in args.properties:
        prop_name = strip_prefix(prop)
        checked += 1

        if not type_exists:
            print(f"ERROR: schema:{type_name} が存在しないため {prop_name} の所属を検証できません")
            errors += 1
            continue

        in_domain = property_in_domain(prop_name, ancestry, properties)
        if in_domain is None:
            print(f"ERROR: {prop_name} は Schema.org 語彙に存在しません")
            errors += 1
        elif in_domain:
            print(f"OK: {prop_name} は schema:{type_name}（またはその祖先型）に属します")
            if args.show_range:
                _print_range(prop_name, properties, types)
        else:
            print(f"ERROR: {prop_name} は schema:{type_name} およびその祖先型のいずれにも属しません")
            errors += 1

    print(f"SUMMARY: type=schema:{type_name}, checked={checked}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
