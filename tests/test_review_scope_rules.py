"""Tests that the machine review states what it does NOT evaluate (Issue #722).

WikiCommit's machine review checks whether a generated page is faithful to the
evidence it was given. Completeness — whether other material could have added
more — is not a criterion. That premise had been operated consistently and
written down nowhere: grepping the distributed Skills for `completeness` /
`comprehensive` returned zero hits, and the evidence-binding rule (Issue #442)
only forbids the *excess* side ("do not write what the source does not say"),
never stating that the *shortfall* side is exempt.

An unwritten premise drifts, which is the failure this repository keeps
re-encountering (Issue #552's schema rule that its own author ignored minutes
later; Issue #571's "a rule with a generation-time instruction and no detector
drifts"). These tests are the detector for those written rules.

**Where they are written changed in Issue #752.** They used to be restated in
each of the three review Skills, and this file checked all three copies —
because nothing else would notice if one was dropped. The three had already
drifted apart by then, so the rules moved into `.wikicommit/review-rules.md`
and these tests moved with them: one copy to check, and
`tests/test_review_rules_single_source.py` separately enforcing that no fourth
copy grows back inside a Skill.

What stays asserted against a Skill is what stayed in one: the *reporting* of a
finding is choreography, and it differs per path — `wikicommit-generate` rolls
registration candidates into its Completion Notice across retry rounds, while
`wikicommit-review` has no retry loop and reports one finding.
"""

from pathlib import Path

REPO = Path(__file__).parent.parent
SKILLS = REPO / ".claude" / "skills"
RULES = SKILLS / "wikicommit-init" / "scripts" / "templates" / "review-rules.md"


def read_skill(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def rules() -> str:
    """The rules file, whitespace-flattened — it is hard-wrapped prose, so a
    phrase long enough to identify a rule straddles a line break."""
    return " ".join(RULES.read_text(encoding="utf-8").split())


def test_completeness_is_declared_not_a_criterion():
    assert "Completeness is not a criterion" in rules(), (
        "the review rules no longer state that completeness is not a criterion. "
        "Without it, a reviewer reading only the evidence-binding rule sees the "
        "excess side forbidden and infers the shortfall side is a defect — which "
        "turns granularity judgments into FAILs that burn generate.max_retries."
    )


def test_the_exemption_is_stated_as_one_sided():
    """The rule must exempt the shortfall side without re-defining the excess
    side. Phrased as "only claims absent from the source can FAIL" it reads as
    an exhaustive list of FAIL conditions and quietly weakens the ones that
    catch claims a source *does* state: an attribution swap (Issue #429), an
    unattributed single-source formulation (Issue #429), and following the
    weaker of two disagreeing sources (Issue #566)."""
    text = rules()
    assert "shortfall" in text, (
        "the review rules no longer name the asymmetry ('shortfall') the "
        "completeness rule depends on."
    )
    assert any(phrase in text for phrase in ("narrows none", "narrows nothing")), (
        "the review rules no longer say the completeness rule narrows none of "
        "the FAIL conditions."
    )
    # The three checks the one-sided phrasing exists to protect must still be there.
    for check in ("Attribution correctness", "Unattributed single-source formulations",
                  "Source-vs-source disagreement"):
        assert check in text, f"the review rules no longer carry the {check!r} check"


def test_external_research_is_ruled_out():
    """Evidence binding says what may count as evidence; it never says not to
    go looking. That one move is what this rule adds — it is an action rule,
    not a fourth restatement of evidence binding (Issue #552)."""
    text = rules()
    assert "Do not research outside what you were given" in text, (
        "the review rules no longer rule out reaching outside the evidence mid-review."
    )
    assert "web search" in text, (
        "the review rules no longer name the specific action ruled out."
    )


def test_rules_distinguish_refetching_a_registered_source():
    """`wikicommit-review` fetches `source.url` with WebFetch. That is
    re-acquiring a source the page already declares, not external research —
    and a reviewer reads both instructions, so the distinction has to be stated
    or they read as contradicting each other."""
    assert "Neither is re-fetching a source the page already declares" in rules()


def test_rules_cover_documents_the_page_cites_but_does_not_hold():
    """A MISSING_SOURCE finding names a document the page cited and the wiki
    does not hold — including one reached only through another source's passing
    mention, which is the loophole that let a secondary citation through in
    practice (Issue #473)."""
    text = rules()
    assert "Cited documents the page does not hold" in text
    assert "Apply this to secondary citations too" in text, (
        "the review rules no longer close the secondary-citation loophole: a "
        "source merely mentioning a document is not that document being present."
    )
    # Scoped to what the review actually holds, not to the page's `sources` field:
    # a translation carries none and inherits the parent's.
    assert "not among the evidence assembled for this review" in text
    assert "never as the page's own `sources` field" in text, (
        "the review rules no longer forbid matching against the `sources` field "
        "itself, so the check fires on every document a translated page names — "
        "starting with the one it was translated from."
    )
    # And a synthesized page names no document to register, on either path that
    # can be pointed at one.
    assert "does not apply to a page carrying `derived_from` on `review-skill`" in text, (
        "the review rules no longer exempt a synthesized page from the "
        "cited-document check on the /wikicommit-review path, so an unbacked "
        "claim there is reported as a document to go register."
    )


def test_generate_rolls_up_missing_source_documents():
    """Reporting is choreography and stays in the Skill. The retry's fix is to
    drop the claim, after which the page passes and the document is forgotten —
    the same shape Issue #315 found in the old better_type_candidate scheme."""
    text = read_skill("wikicommit-generate")
    assert "Harvest the `MISSING_SOURCE` entries from every review round" in text, (
        "wikicommit-generate/SKILL.md no longer harvests MISSING_SOURCE entries "
        "on every round. Gating the harvest on a retry actually happening drops "
        "the final round, whose page goes to failed_pages — exactly the entry "
        "the Completion Notice has to mark as coming from a discarded page."
    )
    assert "not registered as sources" in text, (
        "wikicommit-generate/SKILL.md no longer rolls MISSING_SOURCE documents "
        "up in the Completion Notice."
    )


def test_review_reports_the_same_finding_as_a_registration_candidate():
    """The review path has no retry loop to roll it up into, so it reports one
    finding — but it must still tell the user the document can be registered,
    or the finding dies in the conversation."""
    text = read_skill("wikicommit-review")
    assert "registration candidate" in text, (
        "wikicommit-review/SKILL.md no longer reports a cited-but-unregistered "
        "document as something to register."
    )
    assert "/wikicommit-generate <url-or-path>" in text


def test_synthesize_missing_source_is_excluded_from_that_rollup():
    """Same enum value, different meaning: in synthesis it means *no* grounding
    page states the claim, so there is no document to name — which is why those
    entries leave `source_file` empty (Issue #674). Folding it into the
    registration roll-up would print an empty recommendation to register
    something."""
    text = rules()
    assert "`MISSING_SOURCE` means something different here" in text
    assert "not a document worth registering" in text, (
        "the review rules no longer exempt synthesized pages from the "
        "registration-candidate reading of MISSING_SOURCE."
    )
    # And the detection check itself must say it does not apply there.
    assert "On `synthesize-step5.5` this check does not apply" in text
