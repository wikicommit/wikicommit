#!/usr/bin/env python3
"""Report type schema files that are written in a shape nothing else checks
(Issue #889).

`wikicommit-generate`'s own instructions say "Nothing validates a schema file",
and that was accurate. Files under `.wikicommit/schema/` come from three
origins and CI could only reach one of them:

    provenance: default                      distributed templates — four
                                             tests/test_schema_template_*.py
                                             files hold these to the conventions
    init-theme / collect /                   written at runtime by a Skill —
    generate-interactive /                   nothing checked them
    generate-auto / schema-propose
    manual                                   written by hand — nothing checked
                                             them either

And a schema file cannot be repaired by any Skill afterwards: the narrow
exception that lets one be written is add-only, so a file written in a broken
shape stays broken until a person opens `.wikicommit/schema/` themselves.

Every tool this needs already existed — `check_schema_org_type.py` verifies a
property against the vocabulary, `_schemaorg_vocab.py` resolves a type's
ancestry, `provenance_of()` in check_installed_type_usage.py already reads the
field. What was missing was something that ran them over the files.

## Findings

Blocking nothing. Every line is a report, and `wikicommit-merge` deliberately
does not call this: a repository holding one malformed schema file would
otherwise be unable to merge anything at all, and unlike the page-side `type:`
check (which `wikicommit-generate` can fix on the spot by regenerating), the
fix here is a human editing a file no Skill may touch.

    BAD_PROPERTY    a `properties:` key that is not in the Schema.org
                    vocabulary, or is not in the domain of this file's type
                    (the same check validate_frontmatter.py applies to a page's
                    `properties:`, which never ran against the template the
                    page was generated from)
    MAPPING_BULLET  a `granularity` bullet that parsed as a mapping rather than
                    a string, because an unquoted `": "` turned it into one
    TRUNCATED_BULLET
                    a `granularity` bullet whose raw line carries an unquoted
                    ` #`, which opens a YAML comment and drops the rest of the
                    line. This is the failure mode Issue #649 singled out as
                    the one nothing warns about: the bullet is still a string,
                    so the parsed value looks fine and the missing half is
                    simply gone
    NO_BOUNDARY     no `granularity` bullet begins with `Boundary`
    BAD_PROVENANCE  a `provenance` value that is not one of the seven
                    (Issue #519). **A missing value is not reported** — its
                    absence means "written before that field existed"
    NO_BASE         no `wikicommit.base`
    NO_WIKICOMMIT_BLOCK
                    no `wikicommit:` block at all, so none of the fields above
                    can be there to find
    TYPE_PATH_MISMATCH
                    `type:` disagrees with the path the file sits at, the same
                    check Issue #545 added for pages
    UNKNOWN_TYPE    `type:` and the path agree, and neither is in the Schema.org
                    vocabulary — usually a misspelling, and the file resolves to
                    no type at all. Only reported when the two agree: when they
                    do not, TYPE_PATH_MISMATCH has already named the one thing
                    to fix
    NO_RATIONALE    a custom type with no `wikicommit.rationale` (Issue #548) —
                    for a type outside the vocabulary that prose is the only
                    durable record of why it exists
    NO_FRONTMATTER / UNPARSEABLE
                    the frontmatter is absent or does not parse. Reported as one
                    finding, returning early, since every other check would
                    otherwise fire off that same single cause

## What is deliberately not reported

- **A missing `provenance`.** Issue #519 defined its absence as "made before
  this field existed", so reporting it would light up every older repository
  for a state that is correct.
- **`default.md`.** It carries no `type:` and no `base:` by design, being the
  fallback rather than a type.
- **Anything a custom type's properties or its `base` would have to be resolved
  against.** A custom type is by definition outside the vocabulary, so there is
  nothing to check a property name or a base URL against. Only the checks that
  need no vocabulary run for one — NO_BASE and NO_RATIONALE, which ask whether
  the field is there rather than whether its value resolves, still do.
- **Prose quality in `granularity`.** Whether a rule is *right* is not
  decidable here (Issue #552 reached the same conclusion and stopped at
  strengthening the instructions). This looks only at shape.

Usage:
    python .wikicommit/scripts/check_schema_files.py

Exit code: always 0 (informational, non-blocking, matching
check_schema_coverage.py / check_installed_type_usage.py / etc.).
"""

import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _schemaorg_vocab import (
    SCHEMA_DIR,
    ancestors,
    load_or_build_index,
    property_in_domain,
    strip_prefix,
)

# The seven values of Issue #519, one per write site plus the hand-written case.
KNOWN_PROVENANCE = (
    "default",
    "init-theme",
    "generate-interactive",
    "generate-auto",
    "collect",
    "schema-propose",
    "manual",
)

# A bullet line in the raw text: `    - ` possibly followed by anything.
BULLET_RE = re.compile(r"^\s*-\s+(?P<body>.*)$")


def collect_type_schema_files() -> list[Path]:
    if not SCHEMA_DIR.exists():
        return []
    return sorted(SCHEMA_DIR.rglob("*.md"))


def type_name_from_path(path: Path) -> str:
    """The type a file at this path defines, derived the way every consumer
    derives it: the path under `.wikicommit/schema/` with `.md` removed.

    This is the only derivation there is — nothing scans the directory by type
    name — so a file moved into a subdirectory of the maintainer's own invention
    stops being found at all (Issue #575). Comparing the
    derived name against the file's own `type:` is what turns that silent
    failure into a report.
    """
    return path.relative_to(SCHEMA_DIR).with_suffix("").as_posix()


def granularity_raw_bullets(path: Path) -> list[str]:
    """The raw text of each `granularity` bullet, before YAML sees it.

    A parsed bullet cannot tell you it was truncated: ` #` opens a comment and
    YAML hands back the part before it as a perfectly ordinary string. The only
    way to notice is to read the line as written, which is why this walks the
    text rather than re-parsing.

    Deliberately simple, per Issue #889's second point. It reads the lines
    between `granularity:` and the next key at the same or shallower
    indentation, and takes any that look like a list item. A file whose
    `granularity` is written in YAML flow style (`granularity: [a, b]`) yields
    nothing here, and the parsed-value checks still cover it.

    Scoped to the frontmatter block first, which is not optional: the closing
    `---` is itself a line beginning with `-`, so the "a line that is not a
    bullet ends the list" rule below steps straight over it. Without the slice,
    a file whose `wikicommit:` block happens to come last — YAML key order is
    free, and a hand-written one may well put it there — reads the page
    template's own Markdown list as `granularity` bullets and reports them.
    """
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return []

    if lines and lines[0].startswith("---"):
        end = next(
            (i for i, line in enumerate(lines[1:], 1) if line.rstrip() == "---"), None
        )
        lines = lines[1:end] if end is not None else lines[1:]

    bullets: list[str] = []
    indent = None
    for line in lines:
        if indent is None:
            if re.match(r"^(?P<i>\s*)granularity:\s*$", line):
                indent = len(line) - len(line.lstrip())
            continue
        if not line.strip():
            continue
        current = len(line) - len(line.lstrip())
        if current <= indent and not line.lstrip().startswith("-"):
            break
        match = BULLET_RE.match(line)
        if match:
            bullets.append(match.group("body"))
    return bullets


def unquoted_hash_comment(body: str) -> bool:
    """True if this raw bullet body carries a ` #` that YAML reads as a comment.

    A bullet wrapped in quotes is safe — the `#` is inside the scalar — which is
    exactly the fix the distributed templates use, so a quoted bullet must not
    be reported. Everything else with ` #` in it loses the rest of the line.
    """
    stripped = body.strip()
    if stripped.startswith(('"', "'")):
        return False
    return " #" in body


def check_file(path: Path, index: dict | None) -> tuple[list[tuple[str, str]], str]:
    """Findings for one schema file, as (kind, message) pairs, plus its `provenance`.

    The provenance comes back with the findings because the caller needs it to
    split the count, and re-reading the file to get it would parse every schema
    file twice.
    """
    findings: list[tuple[str, str]] = []
    derived = type_name_from_path(path)
    is_default = derived == "default"
    is_custom = derived.startswith("custom/")

    frontmatter, error = parse_frontmatter(path)
    if not isinstance(frontmatter, dict):
        # Reported as a finding rather than a stderr warning: a schema file whose
        # frontmatter does not parse is the most broken state this script can
        # find, and stderr is where the other scripts put things that are not
        # about the repository's own content.
        findings.append(("UNPARSEABLE", f"frontmatter could not be parsed: {error}"))
        return findings, ""
    if not frontmatter:
        # An empty dict means either "no `---` block at all" or "a block with
        # nothing in it" — the shared parser treats both as not-an-error, because
        # most `.md` files legitimately have no frontmatter. A type schema file is
        # the exception: its frontmatter is the definition. Reported as one finding
        # and returned early, since every other check would otherwise fire off the
        # same single cause.
        findings.append((
            "NO_FRONTMATTER",
            "there is no frontmatter, so this file defines nothing — a type schema file is "
            "its frontmatter (the `wikicommit:` block, `type:`, and the `properties:` template)",
        ))
        return findings, ""

    block = frontmatter.get("wikicommit")
    if not isinstance(block, dict):
        findings.append(("NO_WIKICOMMIT_BLOCK", "there is no `wikicommit:` block"))
        block = {}

    provenance = block.get("provenance")
    provenance = provenance if isinstance(provenance, str) else ""
    if provenance and provenance not in KNOWN_PROVENANCE:
        findings.append((
            "BAD_PROVENANCE",
            f"provenance is {provenance!r}, which is none of: {', '.join(KNOWN_PROVENANCE)}",
        ))

    if not is_default and not isinstance(block.get("base"), str):
        findings.append(("NO_BASE", "there is no `wikicommit.base`"))

    if is_custom and not isinstance(block.get("rationale"), str):
        findings.append((
            "NO_RATIONALE",
            "a custom type has no `wikicommit.rationale` saying why no standard type fits",
        ))

    declared = frontmatter.get("type")
    # Whether `type:` and the path agree gates every later check that resolves
    # the type against the vocabulary. When they disagree, TYPE_PATH_MISMATCH has
    # already named the one thing to fix, and resolving anything against the
    # path-derived name would report it back as though the file had declared it.
    type_matches_path = False
    if not is_default:
        if not isinstance(declared, str) or not declared.startswith("schema:"):
            findings.append((
                "TYPE_PATH_MISMATCH",
                f"`type:` is {declared!r}; a file at this path should declare `schema:{derived}`",
            ))
        elif strip_prefix(declared) != derived:
            findings.append((
                "TYPE_PATH_MISMATCH",
                f"`type:` is {declared!r} but the file sits at {derived}.md, "
                f"and only the path decides which type this file defines",
            ))
        else:
            type_matches_path = True

    granularity = block.get("granularity")
    if isinstance(granularity, list):
        has_boundary = False
        for i, entry in enumerate(granularity):
            if not isinstance(entry, str):
                # A mapping bullet still says what it says — and the bullet that
                # loses to an unquoted `": "` is very often the Boundary one
                # (`Boundary with NewsArticle: ...` is the shape three templates
                # carried before Issue #550 replaced the colon with an em dash).
                # Reading its key keeps NO_BOUNDARY from claiming, on top of
                # MAPPING_BULLET, that a bullet plainly present is absent.
                if isinstance(entry, dict) and any(
                    isinstance(key, str) and key.lstrip().startswith("Boundary") for key in entry
                ):
                    has_boundary = True
                findings.append((
                    "MAPPING_BULLET",
                    f"granularity[{i}] parsed as {type(entry).__name__}, not a string — "
                    f'an unquoted ": " turns a bullet into a one-key mapping that every '
                    f"consumer filtering on strings skips. Use an em dash, or quote the bullet",
                ))
                continue
            if entry.lstrip().startswith("Boundary"):
                has_boundary = True
        if granularity and not has_boundary:
            findings.append((
                "NO_BOUNDARY",
                "no granularity bullet begins with `Boundary` — a new type can state its "
                "boundary against an existing one, but nothing can ever write the reciprocal "
                "statement into the other file, so a missing one is not recoverable later",
            ))
    elif granularity is not None:
        findings.append((
            "MAPPING_BULLET",
            f"wikicommit.granularity is {type(granularity).__name__}, not a list",
        ))

    for i, body in enumerate(granularity_raw_bullets(path)):
        if unquoted_hash_comment(body):
            findings.append((
                "TRUNCATED_BULLET",
                f"granularity bullet {i} carries an unquoted ` #`, which opens a YAML comment "
                f"and drops the rest of the line. Nothing else warns about this shape — the "
                f"bullet is still a string, so the missing half is simply gone. Quote the bullet",
            ))

    # Whether the type exists at all does not depend on the file also carrying a
    # `properties:` block: a misspelled type name is what makes the file define
    # nothing, and it is exactly as silent when there is nothing to resolve
    # against it.
    resolvable = index is not None and not is_custom and type_matches_path
    if resolvable and derived not in index["types"]:
        findings.append((
            "UNKNOWN_TYPE",
            f"`type:` names schema:{derived}, which is not in the Schema.org vocabulary, so "
            f"nothing resolves this file to a type — check the spelling, or put a type that is "
            f"deliberately outside the vocabulary under custom/",
        ))
        resolvable = False

    properties = frontmatter.get("properties")
    if isinstance(properties, dict) and properties and resolvable:
        types, props = index["types"], index["properties"]
        ancestry = ancestors(derived, types)
        for key in properties:
            if not isinstance(key, str):
                continue
            verdict = property_in_domain(key, ancestry, props)
            if verdict is None:
                findings.append(("BAD_PROPERTY", f"properties.{key} is not in the Schema.org vocabulary"))
            elif not verdict:
                findings.append((
                    "BAD_PROPERTY",
                    f"properties.{key} is not in the domain of schema:{derived} or any ancestor",
                ))

    return findings, provenance


def main() -> int:
    files = collect_type_schema_files()
    if not files:
        print("SUMMARY: files=0, findings=0")
        print("NOTE: .wikicommit/schema/ holds no type file, so there was nothing to check")
        return 0

    index, err = load_or_build_index()
    if index is None:
        print(
            f"WARNING: the Schema.org vocabulary could not be loaded, so the property checks "
            f"were skipped: {err}"
        )

    total = 0
    in_templates = 0
    for path in files:
        findings, provenance = check_file(path, index)
        label = f", provenance: {provenance}" if provenance else ""
        for kind, message in findings:
            print(f"{kind}: {path}{label} — {message}")
            total += 1
            if provenance == "default":
                in_templates += 1

    print(f"SUMMARY: files={len(files)}, findings={total}, in_distributed_templates={in_templates}")
    if in_templates:
        print(
            "NOTE: findings on a `provenance: default` file mean this repository holds an older "
            "copy of a distributed template, not that someone wrote it wrong — several of these "
            "conventions were added to the templates after they first shipped. The fix is to take "
            "the upstream diff, which check_distribution_freshness.py reports for the same files; "
            "editing a distributed template by hand puts it back in the way on the next sync."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
