"""Guards "no unfillable key in a distributed template's `properties:`" (Issue #553).

A `properties:` key is only worth distributing if Pass 3 can write a conformant
value for it out of what any wiki already has. `DefinedTerm.inDefinedTermSet`
could not: its only entity range is `DefinedTermSet`, which is not a distributed
type and which no Skill can create, and its only DataType range is `URL` — an
identifier for that same unavailable entity, which a taxonomy living inside one
wiki does not have. Pass 3 could therefore neither fill the key nor decide to
drop it, so the template's `""` rode through into the generated pages: 14 of 43
`DefinedTerm` pages in `dev/pilot-ai-driven-dev-wiki-round5.md` carried the key
and none carried a value.

The check below re-derives that reachability judgement from the Schema.org
vocabulary rather than hard-coding a key list, so a newly added template key
with the same shape fails here instead of quietly shipping. Two base-type keys
match the shape and are deliberately kept — see KEPT_UNFILLABLE — because their
range, while entity-only, has a conformant form that needs no wiki-local type.

Runs off the committed .wikicommit/schemaorg-vocab.json, so it is network-free.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_SCHEMA_DIR = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "schema"
)

sys.path.insert(0, str(REPO_ROOT / ".wikicommit" / "scripts"))
import _schemaorg_vocab as vocab  # noqa: E402
from _frontmatter import parse_frontmatter  # noqa: E402

# Entity-only keys that survive the reachability rule by exception, with the
# reason each is still writable. Both are documented in docs/DesignDoc-data.md
# section 5.2 ("配布テンプレートの properties: に「埋められないキー」を置かない").
KEPT_UNFILLABLE = {
    ("Event", "eventStatus"): (
        "EventStatusType is a Schema.org Enumeration; its members are published, "
        "fixed IRIs (https://schema.org/EventCancelled, ...), so a conformant "
        "value exists without any wiki-local type."
    ),
    ("Organization", "numberOfEmployees"): (
        "QuantitativeValue is a structured value that JSON-LD expresses as a "
        "nested object with a known shape, not as a page to link to."
    ),
}


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


def _distributed_type_names() -> set[str]:
    """Type names a wiki gets from wikicommit-init, i.e. what a [[Type/slug]] can resolve to."""
    return {p.stem for p in TEMPLATE_SCHEMA_DIR.glob("*.md")} - {"default"}


def _template_properties() -> list[tuple[str, str]]:
    """Every (type name, properties key) pair across the distributed templates."""
    pairs = []
    for path in sorted(TEMPLATE_SCHEMA_DIR.glob("*.md")):
        frontmatter = _frontmatter(path)
        type_name = (frontmatter.get("type") or "").removeprefix("schema:")
        if not type_name:
            continue  # default.md carries no type and no properties: block
        for key in (frontmatter.get("properties") or {}):
            pairs.append((type_name, key))
    return pairs


@pytest.fixture(scope="module")
def schemaorg_index():
    # vocab.VOCAB_PATH is relative, so it only resolves when pytest happens to
    # run from the repository root; from anywhere else load_or_build_index()
    # would silently fall through to a network fetch and write a stray
    # schemaorg-vocab.json into the caller's cwd. Point it at the committed
    # copy (and drop the JSON-LD test override, which would otherwise swap in
    # some other test's tiny fixture vocabulary) so this module really is
    # network-free wherever it is invoked from.
    saved_path = vocab.VOCAB_PATH
    saved_override = os.environ.pop(vocab.TEST_VOCAB_PATH_ENV, None)
    vocab.VOCAB_PATH = REPO_ROOT / ".wikicommit" / "schemaorg-vocab.json"
    try:
        index, error = vocab.load_or_build_index()
    finally:
        vocab.VOCAB_PATH = saved_path
        if saved_override is not None:
            os.environ[vocab.TEST_VOCAB_PATH_ENV] = saved_override
    if index is None:
        pytest.skip(f"Schema.org vocabulary unavailable: {error}")
    return index


def test_no_unfillable_property_in_distributed_templates(schemaorg_index):
    """Flag any template properties: key that has no conformant value a wiki could write.

    Unfillable means both of:
      1. no entity range candidate is itself a distributed type, and
      2. the DataType candidates cannot carry the fact alone — there are none, or
         the only one is URL while an entity range is also declared (that URL
         would have to identify the entity condition 1 just ruled out).
    """
    distributed = _distributed_type_names()
    properties = schemaorg_index["properties"]
    types = schemaorg_index["types"]

    unfillable = {}
    for type_name, key in _template_properties():
        candidates = vocab.entity_range_candidates(key, properties, types)
        if candidates is None:
            # Not in the Schema.org vocabulary at all (a typo, or a key added
            # after this repo's schemaorg-vocab.json snapshot), so there is no
            # range to judge reachability against. A key that *is* in the
            # vocabulary but declares no rangeIncludes comes back as ([], [])
            # and is judged below, where empty DataType candidates make it
            # unfillable.
            continue
        entities, datatypes = candidates
        if any(entity in distributed for entity in entities):
            continue
        if datatypes and not (entities and datatypes == ["URL"]):
            continue
        unfillable[(type_name, key)] = (entities, datatypes)

    unexpected = sorted(set(unfillable) - set(KEPT_UNFILLABLE))
    assert not unexpected, (
        "distributed schema template(s) declare a properties: key with no value any "
        "wiki could write, so Pass 3 will leave it as an empty placeholder "
        f"(Issue #553): {[f'{t}.{k} (entities={unfillable[(t, k)][0]}, datatypes={unfillable[(t, k)][1]})' for t, k in unexpected]}. "
        "Either drop the key from the template, or add it to KEPT_UNFILLABLE with "
        "the conformant value form that makes it writable."
    )

    stale = sorted(set(KEPT_UNFILLABLE) - set(unfillable))
    assert not stale, (
        "KEPT_UNFILLABLE lists exception(s) that no longer apply — the key was "
        f"removed from its template or its range changed: {stale}"
    )


def test_defined_term_drops_the_term_set_keys():
    """`inDefinedTermSet` and `termCode` stay out of the distributed DefinedTerm template.

    `termCode` is Text-ranged, so the reachability rule above does not catch it;
    it goes because Schema.org defines it as the code identifying a term *within
    a DefinedTermSet*, leaving it unanchored once that key is gone. Observed
    values were the page's own slug repeated back — the same zero-information
    self-reference Issue #275 rules out for `tags`.
    """
    properties = _frontmatter(TEMPLATE_SCHEMA_DIR / "DefinedTerm.md").get("properties") or {}
    assert "inDefinedTermSet" not in properties
    assert "termCode" not in properties
