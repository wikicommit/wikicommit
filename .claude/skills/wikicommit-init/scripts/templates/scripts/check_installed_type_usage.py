#!/usr/bin/env python3
"""Report installed schema types that pages are not actually using (Issue #565).

check_schema_coverage.py finds the opposite shape — a `type:` in use with no
schema file behind it. Nothing looked for a schema file with no pages in front
of it, and that turns out to be the more common failure. `wikicommit/saitama-city-wiki`
had `Park.md` and `Museum.md` installed and approved by a human, and generated
seven parks and two museums as plain `Place` — in the same batch that added the
type files. Every gate passed: `check_schema_coverage.py` reported zero, because
`Place` does have a schema file.

The cause is structural rather than a slip. `Park` and `Museum` are descendants
of `Place` in Schema.org, so writing a park as a `Place` is not an error, only
coarser — and an ancestor type is always available, always familiar, and always
technically correct. Issue #447 found the same force acting on `DefinedTerm` and
addressed it where types are *proposed*; this is the same force acting where an
already-installed type is *chosen*.

Two findings, deliberately different in strength:

  UNUSED             a type file with zero pages. Either the type was a
                     misjudgment, or generation is not reaching for it.
                     `provenance: default` types are exempt — they ship with
                     every wiki whether or not its subject calls for them, so
                     zero pages says nothing about them. A file with no
                     `provenance` at all predates that field (Issue #519), so
                     config.yml's `schema.base_types` stands in for it.
  ANCESTOR_FALLBACK  pages sit on a type whose descendant is also installed.
                     Suggestive, never conclusive: a wiki with `Park.md` still
                     has legitimate `Place` pages that are not parks. Read it as
                     "worth a look", not "this is wrong".

Neither is blocking. Which type fits a subject is a judgment call, and this
script has no way to make it — it can only point at where one may have gone
coarse.

Usage:
    python .wikicommit/scripts/check_installed_type_usage.py

Exit code: always 0 (warning-only, non-blocking).
"""

import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter
from _schemaorg_vocab import (
    SCHEMA_DIR,
    installed_descendants,
    installed_standard_types,
    load_or_build_index,
    strip_prefix,
)
from _wikilink import ENTITY_DIR, collect_entity_pages

# Types wikicommit-init installs unconditionally. Zero pages for one of these is
# the normal state of a wiki whose subject does not involve that type, so
# reporting it would bury the cases that mean something.
EXEMPT_PROVENANCE = "default"

CONFIG_PATH = Path(".wikicommit/config.yml")


def collect_pages() -> list[Path]:
    return collect_entity_pages(ENTITY_DIR)


def page_counts_by_type() -> dict[str, int]:
    """How many live pages each `type:` value has, keyed without the `schema:` prefix."""
    counts: dict[str, int] = {}
    for page in collect_pages():
        frontmatter, error = parse_frontmatter(page)
        if frontmatter is None:
            print(f"WARNING: {page}: {error}", file=sys.stderr)
            continue
        if frontmatter.get("status") == "removed":
            continue
        type_value = frontmatter.get("type")
        if not isinstance(type_value, str) or not type_value.startswith("schema:"):
            continue
        type_name = strip_prefix(type_value)
        counts[type_name] = counts.get(type_name, 0) + 1
    return counts


def configured_base_types(path: Path = CONFIG_PATH) -> set[str]:
    """`schema.base_types` from config.yml — the types init installs unconditionally.

    Only consulted for a schema file with no `provenance` field at all. That
    absence means "written before Issue #519 added the field", not "not a base
    type", so reading it as anything but exempt would flag every base type of
    every wiki initialized before then — the whole shipped set, on any wiki whose
    subject does not happen to use all of it. config.yml records exactly which
    types init put there, which is the fact `provenance: default` would have
    carried, so it answers the question the missing field cannot.

    Any failure to read it yields an empty set, which only costs a few extra
    UNUSED lines on an old repository — the safe direction for a report.
    """
    if not path.exists():
        return set()
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return set()
    if not isinstance(config, dict):
        return set()
    schema = config.get("schema")
    if not isinstance(schema, dict):
        return set()
    base_types = schema.get("base_types")
    if not isinstance(base_types, list):
        return set()
    return {t for t in base_types if isinstance(t, str) and t.strip()}


def provenance_of(path: Path) -> str:
    frontmatter, _error = parse_frontmatter(path)
    if not isinstance(frontmatter, dict):
        return ""
    block = frontmatter.get("wikicommit")
    if not isinstance(block, dict):
        return ""
    value = block.get("provenance")
    return value if isinstance(value, str) else ""


def main() -> int:
    if not SCHEMA_DIR.exists():
        print("SUMMARY: unused=0, ancestor_fallback=0")
        return 0

    index, err = load_or_build_index()
    if index is None:
        print(f"WARNING: the Schema.org vocabulary could not be loaded, so this check was skipped: {err}")
        print("SUMMARY: unused=0, ancestor_fallback=0")
        return 0
    types = index["types"]

    installed = installed_standard_types(SCHEMA_DIR)
    counts = page_counts_by_type()
    base_types = configured_base_types()

    unused_count = 0
    fallback_count = 0
    for type_name in sorted(installed):
        path = installed[type_name]
        pages = counts.get(type_name, 0)

        if pages == 0:
            provenance = provenance_of(path)
            exempt = provenance == EXEMPT_PROVENANCE or (
                not provenance and type_name in base_types
            )
            if not exempt:
                suffix = f", provenance: {provenance}" if provenance else ""
                print(
                    f"UNUSED: schema:{type_name} ({path}{suffix}) — no page uses "
                    f"this schema file"
                )
                unused_count += 1
            continue

        descendants = installed_descendants(type_name, installed, types)
        if descendants:
            print(
                f"ANCESTOR_FALLBACK: schema:{type_name} has {pages} page(s), but the "
                f"more specific {', '.join('schema:' + d for d in descendants)} "
                f"is also installed (the granularity may be too coarse)"
            )
            fallback_count += 1

    print(f"SUMMARY: unused={unused_count}, ancestor_fallback={fallback_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
