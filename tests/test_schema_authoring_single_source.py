"""The type-writing procedure lives in one file, and must not creep back (Issue #886).

Before this, the same procedure was written out in four Skills at once — 20,031 B
across `wikicommit-init`'s theme-driven proposal, `wikicommit-collect`'s Type
Proposal step, `wikicommit-generate` Pass 2b and `wikicommit-schema-propose`
Step 4. The drift that costs had already happened once: the rule that every
`granularity` bullet must survive YAML parsing as a plain string (Issue #649) was
landed by editing the same paragraph into all four sites, and the next such rule
would have been the same four edits again.

Moving it into `.wikicommit/schema-authoring.md` only helps for as long as it
stays moved, and the way that breaks is not dramatic: someone editing one Skill
adds "and remember to use an em dash" inline because it is convenient, and a
second copy is born. Nothing fails when that happens, which is why it needs a
test — the same argument, and the same lightweight absence-checking shape, as
`tests/test_review_rules_single_source.py`, which guards the first instance of
this pattern.

The accountability assertions run the other way: each Skill must still carry the
three non-negotiables and its own `provenance` value, because "move the
procedure" and "move everything" are one careless cut apart.
"""

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent

sys.path.insert(0, str(REPO / "tools"))
from check_skill_md_lines import instruction_files  # noqa: E402
AUTHORING = REPO / ".claude/skills/wikicommit-init/scripts/templates/schema-authoring.md"

# Every path that writes a .wikicommit/schema/<Type>.md, and the `provenance`
# value it stamps. wikicommit-generate stamps one of two depending on how the
# candidate was approved (Issue #507).
TYPE_WRITING_SKILLS = {
    "wikicommit-init": ("init-theme",),
    "wikicommit-collect": ("collect",),
    "wikicommit-generate": ("generate-interactive", "generate-auto"),
    "wikicommit-schema-propose": ("schema-propose",),
}

# Phrases that only appear when the procedure is being *stated* rather than
# referred to. Each is verbatim from the authoring file, so a copy-paste back
# into a SKILL.md trips this.
PROCEDURE_PHRASES = (
    "Do not name properties from memory of the vocabulary",
    "still write the file, with an empty `properties:` block",
    "Do not go looking for a \"closest existing type\" to copy instead",
    "opens a YAML comment and truncates the rest of the line",
    "Nothing validates a schema file, so a bullet mangled this way is merged",
    "A `granularity` is for what is specific to",
)

# The three things each path stays accountable for even when the Read is skipped,
# so that degradation is thin guidance rather than none.
NON_NEGOTIABLES = ("check_schema_org_type.py", "Boundary —")


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    The authoring file is hard-wrapped prose, so any phrase long enough to
    identify a step will straddle a line break somewhere — and where it breaks
    changes the moment a word is edited. Matching the wrapped text would fail for
    reformatting and pass for a real second copy that wrapped differently, which
    is backwards. SKILL.md files are not wrapped, so normalizing costs nothing
    there.
    """
    return " ".join(text.split())


def authoring_text() -> str:
    return AUTHORING.read_text(encoding="utf-8")


def skill_text(name: str) -> str:
    """Every instruction file the Skill can reach, concatenated.

    Not just `SKILL.md`: Issue #887 moved one mode's procedure into a sibling
    file and Issue #911 put each of `wikicommit-generate`'s passes in
    `references/` — including Pass 2b, which is the site this guard is about for
    that Skill. Reading only `SKILL.md` would report the move as the procedure
    going missing in one direction, and would stop seeing a copy pasted back in
    the other. The rule for "which `.md` under a Skill is instructions" is
    imported rather than restated, so this cannot drift from the size metric and
    the two blocking scanners.
    """
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in instruction_files(REPO / ".claude/skills" / name)
    )


def test_the_authoring_file_exists_and_is_parseable():
    text = authoring_text()
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert isinstance(fm, dict)
    assert isinstance(fm.get("wikicommit"), dict)


def test_applies_to_lists_exactly_the_provenance_values_the_paths_stamp():
    """One vocabulary, so this list and a written file's own `provenance` line up.

    Three of the four paths stamp a value that names themselves; the type-necessity
    pass stamps one of two. A pass name here instead (`generate-pass2b`) would never
    match a `provenance` value, which is the reading a future consumer would take.
    """
    fm = yaml.safe_load(authoring_text().split("---\n")[1])
    listed = fm["wikicommit"]["applies_to"]
    expected = sorted(v for values in TYPE_WRITING_SKILLS.values() for v in values)
    assert sorted(listed) == expected, (
        f"applies_to is {sorted(listed)} but the paths stamp {expected}"
    )


def test_the_file_carries_no_version_field():
    """Deliberate: every reader is the agent itself, so an echo verifies nothing.

    `review-rules.md`'s `rules_version` works because a review subagent echoes it
    back and the orchestrator checks it. Adding one here would look like the same
    guarantee while providing none.
    """
    fm = yaml.safe_load(authoring_text().split("---\n")[1])
    assert "rules_version" not in fm
    assert "rules_version" not in fm["wikicommit"]


def test_every_procedure_phrase_is_in_the_authoring_file():
    """Guards the premise of the test below: these phrases identify the procedure."""
    text = _flat(authoring_text())
    for phrase in PROCEDURE_PHRASES:
        assert _flat(phrase) in text, (
            f"{phrase!r} is not in the authoring file; this test's premise is stale"
        )


def test_the_procedure_is_not_restated_in_any_skill():
    for name in TYPE_WRITING_SKILLS:
        text = _flat(skill_text(name))
        for phrase in PROCEDURE_PHRASES:
            assert _flat(phrase) not in text, (
                f"{name} restates the type-writing procedure ({phrase!r}). "
                f"It belongs in .wikicommit/schema-authoring.md only — a second copy "
                f"is how the four drifted in the first place."
            )


def test_each_skill_points_at_the_authoring_file():
    for name in TYPE_WRITING_SKILLS:
        assert ".wikicommit/schema-authoring.md" in skill_text(name), (
            f"{name} no longer names the authoring file, so nothing tells "
            f"the path to read it"
        )


def test_each_skill_keeps_its_own_non_negotiables_and_provenance():
    """Skipping the Read must leave thin guidance, not none."""
    for name, provenances in TYPE_WRITING_SKILLS.items():
        text = skill_text(name)
        for needle in NON_NEGOTIABLES:
            assert needle in text, (
                f"{name} dropped the {needle!r} non-negotiable, so a run "
                f"that skips the Read has nothing at all to fall back on"
            )
        for provenance in provenances:
            assert provenance in text, (
                f"{name} no longer names the `{provenance}` provenance "
                f"value it is the only place to stamp"
            )


def test_each_skill_falls_back_to_the_skill_tree_copy_before_giving_up():
    """The procedure ships with the Skills, so a stale wiki is not a dead end.

    `.wikicommit/schema-authoring.md` is `update: overwrite`, so it only reaches a
    repository on its next init — every wiki initialized before it shipped is
    without it. The same bytes sit in the Skill tree that is running, and
    `wikicommit-update` Step 2 already takes that route for a script an older
    repository lacks. Without the fallback, every type addition on every existing
    wiki is refused while the procedure is on disk.
    """
    # Written relative to the Skill's own directory since Issue #1021, so the same file
    # is `scripts/templates/…` from wikicommit-init and `../wikicommit-init/scripts/…`
    # from its siblings.
    for name in TYPE_WRITING_SKILLS:
        text = skill_text(name)
        expected = (
            "scripts/templates/schema-authoring.md" if name == "wikicommit-init"
            else "../wikicommit-init/scripts/templates/schema-authoring.md"
        )
        assert expected in text, (
            f"{name} gives up when .wikicommit/schema-authoring.md is "
            f"absent without trying the Skill-tree copy"
        )


def test_the_custom_type_path_is_also_told_to_write_granularity_this_way():
    """A custom type carries `granularity` too, and its path skips Step 4 entirely.

    `wikicommit-schema-propose` Step 3 routes a name the vocabulary does not have
    to Step 5, which never reaches Step 4's pointer — so if only Step 4 names the
    authoring file, the YAML-string discipline reaches standard types only.
    """
    text = skill_text("wikicommit-schema-propose")
    custom = text.split("### Step 5: Custom type path", 1)
    assert len(custom) == 2, "Step 5's heading moved; this test can no longer scope to it"
    body = custom[1].split("### Step 6", 1)[0]
    assert ".wikicommit/schema-authoring.md" in body, (
        "the custom-type path does not name the authoring file, so nothing states "
        "the granularity discipline for a custom type"
    )
