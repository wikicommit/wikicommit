"""The review discipline lives in one file, and must not creep back (Issue #752).

Before this, the same rules were written out in three Skills at once — 27KB
across `wikicommit-generate` Pass 4, `wikicommit-review` Step 4 and
`wikicommit-synthesize` Step 5.5 — and the three had already drifted: checks
that existed in only one of them, and no decision on record about which version
was right.

Moving them into `.wikicommit/review-rules.md` only helps for as long as they
stay moved. The way that breaks is not dramatic: someone editing one Skill adds
"and remember to check attributions" inline because it is convenient, and a
second copy is born. Nothing fails when that happens, which is why it needs a
test.

This enforces *absence* rather than content equality, the same lightweight
pattern `tests/test_schema_template_boundary_rules.py` uses. It cannot tell
paraphrase from restatement, so it keys on the distinctive phrases each rule
actually uses — enough to catch a copy-paste, which is the realistic failure.

The choreography assertions run the other way: they check that the steps which
must NOT have moved are still in their Skill, because "move the discipline" and
"move everything" are one careless cut apart.
"""

from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent
RULES = REPO / ".claude/skills/wikicommit-init/scripts/templates/review-rules.md"

REVIEW_SKILLS = {
    "wikicommit-generate": REPO / ".claude/skills/wikicommit-generate/SKILL.md",
    "wikicommit-review": REPO / ".claude/skills/wikicommit-review/SKILL.md",
    "wikicommit-synthesize": REPO / ".claude/skills/wikicommit-synthesize/SKILL.md",
}

# Phrases that only appear when a rule is being *stated* rather than referred to.
# Each is verbatim from the rules file, so a copy-paste back into a SKILL.md trips it.
DISCIPLINE_PHRASES = (
    "is a *source-to-claim* check, not a *fact* check",
    "**never** on your own pretrained",
    "Do not fill gaps in the evidence from your training data",
    "Completeness is not a criterion",
    "prefer the one that **treats that fact's subject as its own subject**",
    "a list, index, directory, or roster entry is weaker evidence",
    "Naming a practice and originating it are different",
    "the attribution itself is the defect",
    "add attribution phrasing",
)

# The steps that must stay in their Skill: launching, retrying, writing, status.
CHOREOGRAPHY = {
    "wikicommit-generate": (
        "generate.max_retries",
        "failed_pages",
        "reset_review_on_content_change.py",
        "record_review.py",
        "Update the source management file's status locally",
    ),
    "wikicommit-review": (
        "gh issue close",
        "set_frontmatter_field.py",
        "record_review.py",
    ),
    "wikicommit-synthesize": (
        "generate.max_retries",
        "rebuild_index.py",
        "record_review.py",
    ),
}


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    The rules file is hard-wrapped prose, so any phrase long enough to identify a
    rule will straddle a line break somewhere — and where it breaks changes the
    moment a word is edited. Matching on the wrapped text would make this suite
    fail for reformatting and pass for a real second copy that happened to wrap
    differently, which is backwards. SKILL.md files are not wrapped, so
    normalizing costs nothing there.
    """
    return " ".join(text.split())


def rules_text() -> str:
    return RULES.read_text(encoding="utf-8")


def test_the_rules_file_exists_and_is_parseable():
    text = rules_text()
    assert text.startswith("---\n")
    fm = yaml.safe_load(text.split("---\n")[1])
    assert isinstance(fm, dict)
    assert isinstance(fm.get("rules_version"), int), (
        "rules_version must be an integer a subagent can echo back verbatim"
    )


def test_every_discipline_phrase_is_in_the_rules_file():
    """Guards the premise of the test below: these phrases identify the rules."""
    text = _flat(rules_text())
    for phrase in DISCIPLINE_PHRASES:
        assert _flat(phrase) in text, f"{phrase!r} is not in the rules file; this test's premise is stale"


def test_the_discipline_is_not_restated_in_any_skill():
    for name, path in REVIEW_SKILLS.items():
        text = _flat(path.read_text(encoding="utf-8"))
        for phrase in DISCIPLINE_PHRASES:
            assert _flat(phrase) not in text, (
                f"{name}/SKILL.md restates the review discipline ({phrase!r}). "
                f"It belongs in .wikicommit/review-rules.md only — a second copy is "
                f"how the three drifted apart in the first place."
            )


def test_each_skill_points_at_the_rules_file():
    for name, path in REVIEW_SKILLS.items():
        text = path.read_text(encoding="utf-8")
        assert ".wikicommit/review-rules.md" in text, (
            f"{name}/SKILL.md no longer names the rules file, so nothing tells the "
            f"review to read it"
        )


def test_each_skill_stops_when_the_rules_file_is_missing():
    """Fail-open would degrade the review silently *and* record it as having happened."""
    for name, path in REVIEW_SKILLS.items():
        text = path.read_text(encoding="utf-8")
        assert "does not exist" in text and "/wikicommit-init --no-overwrite" in text, (
            f"{name}/SKILL.md does not say what to do when the rules file is absent"
        )


def test_the_two_subagent_paths_verify_the_echoed_rules_version():
    """wikicommit-review reads the rules itself, so it has nothing to verify."""
    for name in ("wikicommit-generate", "wikicommit-synthesize"):
        text = REVIEW_SKILLS[name].read_text(encoding="utf-8")
        assert "rules_version" in text, f"{name}/SKILL.md does not check the echo"
        # Not a bare "once": that matches incidental prose ("once per run") in a
        # thousand-line file, so the assertion could never fail for its own reason.
        assert "Relaunch" in text, (
            f"{name}/SKILL.md no longer says to relaunch the subagent when the echo "
            f"is missing or wrong"
        )


def test_the_two_subagent_paths_hand_the_subagent_its_path_label():
    """The rules scope checks by path, so a subagent that is not told which path
    it is on has to guess — and guessing `review-skill` inside Pass 4 means
    "report findings; do not decide", i.e. no verdict for the retry loop to route
    and no cross-page check even though the one-hop pages were assembled for it.
    The "and nothing else" bound above makes this worse, not better: it forbids
    adding the label unless the list itself carries it."""
    for name, stage in (
        ("wikicommit-generate", "generate-pass4"),
        ("wikicommit-synthesize", "synthesize-step5.5"),
    ):
        text = REVIEW_SKILLS[name].read_text(encoding="utf-8")
        assert stage in text, (
            f"{name}/SKILL.md never names the path label {stage!r}, so nothing "
            f"tells the subagent which of the rules file's per-path sections is its own"
        )


def test_the_rules_file_says_where_the_path_label_comes_from():
    text = _flat(rules_text())
    assert "Your path is stated in your prompt" in text, (
        "the rules file scopes checks by path but no longer says where the "
        "reviewer learns its path, which leaves it guessing"
    )


def test_the_two_subagent_paths_state_the_sender_side_contract():
    """The receiver-side rule cannot stop the sender from over-sharing."""
    for name in ("wikicommit-generate", "wikicommit-synthesize"):
        text = REVIEW_SKILLS[name].read_text(encoding="utf-8")
        assert "and nothing else" in text, (
            f"{name}/SKILL.md does not bound what goes into the subagent's prompt"
        )
        assert "SOURCE" in text


def test_the_choreography_did_not_move():
    for name, markers in CHOREOGRAPHY.items():
        text = REVIEW_SKILLS[name].read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, (
                f"{name}/SKILL.md lost {marker!r}. Issue #752 moved the discipline only; "
                f"retries, failure handling, writing and status updates stay in the Skill."
            )


def test_the_rules_file_separates_common_rules_from_per_path_differences():
    text = _flat(rules_text())
    assert "Rules that hold on every path" in text
    assert "Differences by path" in text
    for stage in ("generate-pass4", "review-skill", "synthesize-step5.5"):
        assert stage in text, f"the rules file does not address the {stage} path"


def test_the_rules_file_carries_the_receiver_side_defense():
    text = _flat(rules_text())
    assert "Only what is marked `SOURCE` is evidence" in text
    # The specific things a generator would otherwise leak into the prompt.
    for leak in ("summary", "analysis JSON", "previous review round"):
        assert leak in text, f"the rules file does not name {leak!r} as non-evidence"
