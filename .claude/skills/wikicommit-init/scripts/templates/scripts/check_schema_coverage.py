#!/usr/bin/env python3
"""Detect `type:` values used by wiki pages that have no dedicated schema file.

For each wiki page under .wikicommit/entity/**/*.md (excluding index.md and
status: removed pages), reads its `type:` frontmatter field and checks
whether a matching file exists under .wikicommit/schema/
(schema:Person -> Person.md, schema:custom/Decision -> custom/Decision.md).
Falling back to default.md does not count as "covered" — a type that only
resolves via the default.md fallback is exactly the coverage gap
wikicommit-schema-propose (Issue #285) exists to detect and fill.

Type strings are aggregated by exact match only — no normalization or fuzzy
matching (kept deterministic and simple; a known limitation documented in
Issue #285's design notes: the same real-world concept can end up split
across multiple slightly different type strings over time).

Usage:
    python .wikicommit/scripts/check_schema_coverage.py

Exit code: always 0 (informational, non-blocking).
"""

import sys
from collections import defaultdict
from pathlib import Path

from _frontmatter import parse_frontmatter_or_warn
from _wikilink import ENTITY_DIR
SCHEMA_DIR = Path(".wikicommit/schema")


def collect_pages() -> list[Path]:
    if not ENTITY_DIR.exists():
        return []
    return sorted(
        p for p in ENTITY_DIR.rglob("*.md")
        if "assets" not in p.parts and p.name != "index.md"
    )


def has_dedicated_schema_file(type_value: str) -> bool:
    """True if type_value resolves to its own .wikicommit/schema/ file
    (not merely the default.md fallback). Non-'schema:'-prefixed values are
    validate_frontmatter.py's concern, not this script's — treated as
    covered here so they are not double-reported."""
    if not type_value.startswith("schema:"):
        return True
    type_name = type_value[len("schema:"):]
    return (SCHEMA_DIR / f"{type_name}.md").exists()


def main() -> int:
    pages_by_type: dict[str, list[str]] = defaultdict(list)

    for page in collect_pages():
        fm = parse_frontmatter_or_warn(page)
        if not fm or fm.get("status") == "removed":
            continue
        type_value = fm.get("type")
        if not isinstance(type_value, str) or not type_value:
            continue
        if not has_dedicated_schema_file(type_value):
            pages_by_type[type_value].append(str(page))

    for type_value in sorted(pages_by_type):
        pages = pages_by_type[type_value]
        print(f"UNCOVERED: {type_value} ({len(pages)} pages, e.g. {pages[0]})")

    print(f"SUMMARY: unschemaed_types={len(pages_by_type)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
