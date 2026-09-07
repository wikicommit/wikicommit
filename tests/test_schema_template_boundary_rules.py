"""Guards the "every base type states its own boundary" convention (Issue #550).

`wikicommit-generate` Pass 2b may only *add* a `.wikicommit/schema/<Type>.md`
file — no Skill can edit an existing one. So when a dynamically added type
writes a boundary rule against an installed type, the reciprocal statement can
never be written back into the installed type's own file. The asymmetry that
produces is structural, not a one-off mistake: only the newer type ends up
saying where the line is, and type selection drifts toward whichever side of a
boundary happens to have documented it.

`dev/pilot-ai-driven-dev-wiki-round5.md` hit this with `HowTo`, whose
`granularity` said nothing about what a HowTo is *not* while a runtime-generated
`TechArticle.md` did. The countermeasure is that every distributed base type
carries a self-sufficient boundary rule of its own, phrased so it holds without
reference to any type that may not be installed.

Two things are checked here, because both failed in practice:

1. Every `schema.base_types` entry has a `granularity` bullet starting with
   "Boundary".
2. Every `granularity` bullet — in every schema template, base type or not —
   parses as a *string*. A top-level ": " inside an unquoted YAML list item
   silently turns the bullet into a single-key mapping instead, which every
   Python consumer that filters on `isinstance(g, str)` then skips without a
   word (`check_property_wikilink_reinforcement.py`'s `is_reinforced` does
   exactly that). Three of the pre-existing "Boundary with X: ..." bullets were
   already invisible to it this way before Issue #550 rewrote them with an
   em dash.
"""

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
TEMPLATE_SCHEMA_DIR = TEMPLATES_DIR / "schema"

sys.path.insert(0, str(REPO_ROOT / ".wikicommit" / "scripts"))
from _frontmatter import parse_frontmatter  # noqa: E402


def _frontmatter(path: Path) -> dict:
    """Return the parsed YAML frontmatter block of a schema template.

    Delegates to the shared production parser rather than splitting here: four
    tests in this directory read the same template set, and each carrying its
    own split is how `.wikicommit/scripts/_frontmatter.py` came to exist in the
    first place (Issue #704 — its module docstring lists the real bugs the
    divergent copies produced). Its path-based entry point is the one used, so
    the BOM handling that docstring names first is inherited along with the
    split; reading the file here with plain utf-8 would leave a BOM-prefixed
    template looking like one with no frontmatter at all.
    """
    frontmatter, error = parse_frontmatter(path)
    assert not error, f"{path}: {error}"
    assert frontmatter, f"{path}: frontmatter block is missing or empty"
    return frontmatter


def _granularity(path: Path) -> list:
    return (_frontmatter(path).get("wikicommit") or {}).get("granularity") or []


def _base_types() -> list[str]:
    config = yaml.safe_load((TEMPLATES_DIR / "config.yml").read_text(encoding="utf-8"))
    return config["schema"]["base_types"]


def test_every_base_type_states_a_boundary_rule():
    missing = [
        type_name
        for type_name in _base_types()
        if not any(
            isinstance(rule, str) and rule.startswith("Boundary")
            for rule in _granularity(TEMPLATE_SCHEMA_DIR / f"{type_name}.md")
        )
    ]
    assert not missing, (
        "base type(s) with no self-sufficient boundary rule in wikicommit.granularity: "
        f"{missing}. Add a bullet starting with 'Boundary' saying what the type is not for "
        "(Issue #550). Phrase it without depending on a type that may not be installed."
    )


def test_granularity_bullets_are_plain_strings():
    offenders = []
    for path in sorted(TEMPLATE_SCHEMA_DIR.rglob("*.md")):
        for rule in _granularity(path):
            if not isinstance(rule, str):
                offenders.append((path.relative_to(REPO_ROOT).as_posix(), rule))

    assert not offenders, (
        "granularity bullet(s) did not parse as strings: "
        f"{offenders}. An unquoted ': ' makes YAML read the bullet as a mapping, which every "
        "consumer filtering on isinstance(g, str) then skips silently. Use an em dash (—) "
        "instead, or quote the whole bullet (Issue #550)."
    )


def test_granularity_bullets_are_not_truncated_by_yaml_comments():
    """An unquoted ' #' opens a YAML comment and silently drops the rest of the bullet.

    Third sibling of the two checks above, same failure shape: the bullet still
    parses, and still parses as a string, so neither existing check notices —
    only its content is gone. Issue references are written as "(Issue #NNN)", so
    a reference placed anywhere but the very end of an unquoted bullet discards
    everything after it. Issue #551's DefinedTerm bullet lost 714 of its 923
    characters this way, and the pre-existing Issue #451 bullet 513 of its 920.
    """
    offenders = []
    for path in sorted(TEMPLATE_SCHEMA_DIR.rglob("*.md")):
        rules = _granularity(path)
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s{4}- (.*\S)\s*$", raw_line)
            if match is None:
                continue
            source = match.group(1)
            if source.startswith(("\"", "'", ">", "|")):
                continue  # quoted or block scalar — ' #' is literal there
            parsed = next(
                (r for r in rules if isinstance(r, str) and source.startswith(r[:40])),
                None,
            )
            if parsed is not None and len(parsed) < len(source):
                offenders.append(
                    (
                        path.relative_to(REPO_ROOT).as_posix(),
                        len(source) - len(parsed),
                        source[:60],
                    )
                )

    assert not offenders, (
        "granularity bullet(s) lost characters to a YAML comment "
        f"(path, chars dropped, bullet start): {offenders}. An unquoted ' #' starts a "
        "comment and discards the rest of the bullet. Quote the whole bullet (Issue #551)."
    )
