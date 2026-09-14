"""Every Skill's `description` parses, and the five distributed model-invocable
ones say when to use them (Issue #912).

Two separate properties, in one file because they are both about the same three
lines of frontmatter.

The first is a trap, not a preference. Frontmatter is written as unquoted plain
scalars, so a `: ` anywhere in a description makes YAML read it as a nested
mapping and **the whole frontmatter stops parsing** — the same failure the
`granularity` bullets hit in Issue #649, in a field that is one of two the
standard requires. It is not hypothetical: writing this Issue's descriptions
produced it twice in five.

**That trap has to be checked against the raw line, not the parsed value.** A
description carrying it never reaches a parsed value at all — `yaml.safe_load`
raises first — so a check on `fm["description"]` can only ever fire on the one
input where `: ` is harmless (a *quoted* scalar), and would then report the
opposite of the truth. The raw-line check below runs before the parse check so
that the trap is named rather than surfacing as a bare `ScannerError`.

The second property is what the official guidance calls the primary triggering
mechanism: a description that says only what a Skill does gives a model nothing
to match a request against, and the guidance's own note is that models
*under*trigger. It applies only where a model can trigger at all. **Seven Skills
lack `disable-model-invocation`, not five** — the set enforced below is the five
*distributed* ones. The other two are the dev-only Skills, which are
model-invocable for the reason Issue #927 settled, and whose descriptions do say
when to use them; they are left unenforced rather than exempt (see the last
test).
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SKILLS = REPO / ".claude" / "skills"

sys.path.insert(0, str(REPO / ".wikicommit" / "scripts"))
from _frontmatter import parse_frontmatter  # noqa: E402

# The *distributed* Skills a model may invoke on its own — read-only ones, by
# deliberate design (see docs/DesignDoc-skills.md section 11.1). Not every
# model-invocable Skill in the tree: the two internal ones lack the flag too, and
# are covered by neither test (see the last one). Listed rather than derived so
# that dropping `disable-model-invocation` from a distributed writing Skill fails
# in this file instead of quietly widening what a model may start by itself.
MODEL_INVOCABLE = {
    "wikicommit-ask",
    "wikicommit-quiz",
    "wikicommit-search",
    "wikicommit-serve",
    "wikicommit-status",
}


def _frontmatter(path: Path) -> dict:
    """Shared with every other frontmatter reader in the repository (BOM handling,
    non-mapping detection, unterminated blocks). Reports a malformed block as a
    message rather than a traceback — which matters here, because the very thing
    the colon rule below guards against is a YAML parse failure."""
    fm, err = parse_frontmatter(path)
    assert not err, (
        f"{path}: {err}. If the description contains ': ', that is the cause — YAML "
        f"reads the rest of the line as a mapping in an unquoted scalar. Use a dash."
    )
    assert fm, f"{path} has no frontmatter"
    return fm


def _skills() -> list[Path]:
    return sorted(SKILLS.glob("*/SKILL.md"))


def _raw_description_value(path: Path) -> str | None:
    """The text to the right of `description:` exactly as written, before YAML
    touches it. Returns None when the description is not a single-line plain
    scalar — a quoted or block scalar carries no `: ` trap to check."""
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None
    lines = text.split("\n")
    for line in lines[1:]:
        if line.rstrip() == "---":
            return None
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value.startswith(('"', "'", ">", "|")) or not value:
                return None
            return value
    return None


def test_no_description_contains_a_colon_followed_by_a_space():
    """Checked on the raw line: a description carrying this never parses, so by
    the time there is a value to inspect the failure has already happened."""
    for path in _skills():
        value = _raw_description_value(path)
        if value is None:
            continue
        assert ": " not in value, (
            f"{path}'s description contains ': ', which YAML reads as a mapping in an "
            f"unquoted scalar — the frontmatter will not parse. Use a dash instead."
        )


def test_every_skill_frontmatter_parses_and_carries_the_two_required_keys():
    for path in _skills():
        fm = _frontmatter(path)
        for key in ("name", "description"):
            assert fm.get(key), f"{path} has no {key}"
        assert fm["name"] == path.parent.name, (
            f"{path} declares name {fm['name']!r} but sits in {path.parent.name!r}; "
            f"`npx skills add --skill <name>` resolves on the declared name"
        )


def test_the_model_invocable_skills_say_when_to_use_them():
    """Not a style rule: for these five the description is the only thing a model
    matches a request against, and among the distributed Skills only these five
    can be matched at all (the two internal ones can too — see the last test)."""
    for name in sorted(MODEL_INVOCABLE):
        fm = _frontmatter(SKILLS / name / "SKILL.md")
        assert "disable-model-invocation" not in fm, (
            f"{name} now disables model invocation, so its description is no longer a "
            f"trigger — move it out of MODEL_INVOCABLE and out of this expectation"
        )
        assert "Use this" in fm["description"], (
            f"{name}'s description no longer says when to use it, only what it does. "
            f"That is the half a model matches a request against (Issue #912)."
        )


def test_every_other_distributed_skill_still_disables_model_invocation():
    """The other direction, for the distributed Skills: these write to the
    repository, open PRs, or merge — a model starting one on its own judgment is
    not something the description rule should be allowed to quietly enable.

    **The two internal Skills are outside this, and that is a real gap rather
    than a neutral exemption.** `metadata.internal: true` is the signal the whole
    repository uses to separate distributed from dev-only (see
    tests/test_skill_distribution_signals_agree.py, which keeps that signal
    honest), so skipping on it keeps this test to the distributed set. But the
    two dev-only Skills — one commits and opens a draft PR, the other
    squash-merges to the default branch — set neither `metadata.internal`'s
    counterpart `disable-model-invocation` nor anything else, so both are
    model-invocable today: the two Skills with the most side effects in the tree
    are the only ones this guard does not cover. Whether they should set it was
    settled in Issue #927, and the answer is no — `disable-model-invocation`
    blocks model invocation outright, and the sequential-loop prompt in
    dev/claude-code-web-setup.md section 2 has the model itself invoke both, once
    per Issue in a list. Locking them stops that loop dead in an unattended cloud
    session. The gap above is therefore accepted, not closed; what changed
    instead is the two descriptions, which now say when to use each so that they
    fire inside that loop and not elsewhere."""
    for path in _skills():
        name = path.parent.name
        fm = _frontmatter(path)
        if name in MODEL_INVOCABLE or (fm.get("metadata") or {}).get("internal"):
            continue
        assert fm.get("disable-model-invocation") is True, (
            f"{name} no longer sets disable-model-invocation: true, so a model may now "
            f"start it on its own. If that is intended, it also needs a 'when to use' "
            f"description and a place in MODEL_INVOCABLE."
        )
