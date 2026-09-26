"""Tests that the three places describing what to do about a retracted source
agree with each other, and with what Regeneration Mode actually does
(Issues #737 / #744).

`status: retracted` is written by a human and never by a Skill, so nothing in
the pipeline enforces the routes out of it — the routes live entirely in prose,
in three copies that ship independently:

- `wikicommit-generate`'s `references/regenerate.md` — the Skill that performs the rebuild
  (the procedure moved out of its SKILL.md in Issue #887; the SKILL.md keeps only
  a branch and a read instruction, so it is the sibling file these assertions read)
- `wikicommit-status` SKILL.md Step 12 — where a human is told which route to take
- `check_retracted_sources.py`'s docstring — the same advice next to the code

plus the design record those three are written from (`docs/DesignDoc-data.md`
and `docs/DesignDoc-ScriptSpec.md`), which does not ship but is where the next
editor looks first.

These three drifted apart once already, within a single pull request: Issue
#737 landed with `--regenerate` re-acquiring every source, so all three
correctly said `--regenerate` was *not* the way to rebuild from what was left.
Issue #744 then made `--regenerate` drop the retracted source, which inverted
that advice. Nothing but these tests notices if one copy keeps the old answer,
and the failure mode is a user following documented advice into the exact
re-ingestion the retraction exists to prevent.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SKILLS = REPO_ROOT / ".claude" / "skills"
# Regeneration Mode's procedure, split out of wikicommit-generate/SKILL.md so that
# an ordinary generation run does not carry it (Issue #887).
REGENERATE = SKILLS / "wikicommit-generate" / "references" / "regenerate.md"
DOCS = REPO_ROOT / "docs"
CHECK_SCRIPT = (
    SKILLS / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_retracted_sources.py"
)

# Each source of advice, and how to read it.
ADVICE_SOURCES = [
    pytest.param(REGENERATE, id="generate-regenerate-md"),
    # Its SKILL.md as well as the sibling file: the procedure moved, but the
    # SKILL.md still ships a summary of this mode, so it is still a place the
    # pre-Issue #744 advice could be written back into. Scanning only the file
    # the procedure moved to would narrow this guard for the same reason
    # Issue #887 had to widen the two Skill scanners.
    pytest.param(SKILLS / "wikicommit-generate" / "SKILL.md", id="generate-skill"),
    pytest.param(SKILLS / "wikicommit-status" / "SKILL.md", id="status-skill"),
    pytest.param(CHECK_SCRIPT, id="check-script-docstring"),
    # The design record is a fourth copy. It does not ship, so it is not one of
    # the three above, but it is where the other three are written from: leave
    # it out and reverting it is invisible to every test here.
    pytest.param(DOCS / "DesignDoc-data.md", id="design-doc-data"),
    pytest.param(DOCS / "DesignDoc-ScriptSpec.md", id="design-doc-scriptspec"),
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", ADVICE_SOURCES)
def test_no_copy_still_says_regenerate_is_not_the_route(path):
    """The pre-Issue #744 wording must not survive anywhere.

    Its exact phrasings are matched rather than a keyword, because the same
    words appear legitimately in the corrected text; what must be gone is the
    claim that `--regenerate` does not work for this.
    """
    text = read(path)
    stale_claims = [
        # wikicommit-status SKILL.md Step 12
        "is not by itself the fix",
        # check_retracted_sources.py's docstring
        "is **not** on its own the way",
        # docs/DesignDoc-data.md — Japanese, and so unmatchable in the three
        # English copies; it is listed because the file carrying it is now
        # scanned, not as a check on the others.
        "はそれ単体では",
        # wikicommit-generate's regenerate.md (and, before Issue #887 moved it,
        # its SKILL.md) — its own pre-Issue #744 wording, which none of the
        # phrasings above ever appeared in. Without this entry the parametrized
        # cases for the files that perform the rebuild cannot fail.
        "disqualifies the page the same way",
    ]
    for claim in stale_claims:
        assert claim not in text, (
            f"{path} still carries the pre-Issue #744 advice ({claim!r}), which "
            "sends a user to /wikicommit-fix for a rebuild that --regenerate now "
            "performs correctly."
        )


def test_regeneration_mode_drops_the_retracted_source_rather_than_the_page():
    """A retracted source is the one acquisition failure that must NOT skip the
    page. The changed / unavailable / manual cases skip because the content is
    still wanted and cannot be had; a retraction says the content is not wanted,
    so removing what rested on it is the point (Issue #744)."""
    text = read(REGENERATE)
    assert "A retracted source is dropped, not fetched, and not carried forward" in text
    assert "drop the retracted entry from the rebuilt page's `sources:`" in text
    # The asymmetry has to be stated, not just implemented: without it the next
    # editor reads the three neighbouring "skip the page" rules and makes this
    # one match them.
    assert "This is the opposite treatment from the changed/unavailable/`manual` cases" in text


def test_a_page_with_no_surviving_source_is_excluded_up_front():
    """Dropping every source would rebuild a page from nothing, so the
    all-retracted page is an eligibility exclusion — which also keeps it from
    consuming one of the five slots in the count guard."""
    text = read(REGENERATE)
    assert "A page **every** one of whose sources is `status: retracted`" in text
    assert "/wikicommit-remove" in text


def test_sources_copy_through_rule_names_its_one_exception():
    """Step 2 says `sources:` is copied through untouched. Left unqualified it
    contradicts step 1's drop, and a reader following step 2 alone would write
    the retracted entry back."""
    text = read(REGENERATE)
    assert "The single exception is a `status: retracted` entry" in text


def test_the_unchanged_output_valve_is_documented_as_unreachable_here():
    """`sources:` is inside the valve's comparison, so a dropped entry always
    counts as a difference. That is the correct outcome — what the page rests
    on changed — but it has to be written down, or a later reader tries to make
    the valve fire for these pages."""
    text = read(REGENERATE)
    assert "can never compare identical and always lands on `pending`" in text


# --- the reference side (Issue #928) -----------------------------------------
#
# Issue #737 listed three holes a retraction had to plug, all on the ingest
# side. Issue #918 found a fourth on the reference side and closed one of its
# three paths (`/wikicommit-ask --include-source`). The other two —
# `/wikicommit-review` and `/wikicommit-fix` — re-fetch a page's `sources[]`
# and read the documents directly, without going through
# `resolve_source_cache_path.py`, so that guard could not reach them.
#
# Review was the sharp one: its whole job is judging whether a page is faithful
# to its sources, so a withdrawn source left in the evidence set meant passing
# a page for being faithful to a document a person had judged unreliable. The
# contradiction sat inside one file — the same SKILL.md tells a reviewer to
# write `status: retracted`, and then ignored it on the next run.
#
# All of this lives in prose, which is why it is asserted here.

GUARDED_SKILLS = [
    pytest.param(SKILLS / "wikicommit-review" / "SKILL.md", id="review-skill"),
    pytest.param(SKILLS / "wikicommit-fix" / "SKILL.md", id="fix-skill"),
]

LIST_COMMAND = "check_retracted_sources.py --list"


@pytest.mark.parametrize("path", GUARDED_SKILLS)
def test_both_reference_paths_still_run_the_guard(path):
    text = read(path)
    assert LIST_COMMAND in text, (
        f"{path} no longer runs `{LIST_COMMAND}`, so it reads source documents a "
        "human has withdrawn. Nothing else on this path notices: the page is "
        "faithful to the withdrawn document, so every automated check passes."
    )


# Anchors are per-file and deliberately narrow: both Skills mention translated
# pages, and `wikicommit-review` walks `sources` in an earlier step too, so a
# loose anchor finds the wrong occurrence and the ordering assertion below
# stops meaning anything.
@pytest.mark.parametrize(
    "path, inherit_anchor, fetch_anchor",
    [
        pytest.param(
            SKILLS / "wikicommit-review" / "SKILL.md",
            "read the parent page's `sources` instead",
            "- For each element of `sources`:",
            id="review-skill",
        ),
        pytest.param(
            SKILLS / "wikicommit-fix" / "SKILL.md",
            "use the parent page's `sources` instead",
            "For each element of `sources`, get the source document",
            id="fix-skill",
        ),
    ],
)
def test_the_guard_runs_before_the_fetch_and_after_sources_is_settled(
    path, inherit_anchor, fetch_anchor
):
    """Both halves of the placement are load-bearing, and both fail quietly.

    Fetching first puts the withdrawn text into context, after which "do not use
    it" rests on instruction-following rather than on never having read it.
    Guarding before the `sources` list is settled misses translated pages
    entirely, since those carry no `sources` of their own and inherit the
    parent's at the step just above.
    """
    text = read(path)
    for anchor in (LIST_COMMAND, inherit_anchor, fetch_anchor):
        assert text.count(anchor) == 1, f"{path}: {anchor!r} is no longer unique"
    assert text.index(inherit_anchor) < text.index(LIST_COMMAND) < text.index(fetch_anchor), (
        f"{path}: the retraction guard must sit after the `translated_from` "
        "fallback and before the per-element fetch."
    )


@pytest.mark.parametrize("path", GUARDED_SKILLS)
def test_neither_skill_writes_the_retraction_itself(path):
    """`status: retracted` is a human's call, and only a human's (Issue #737).

    Both files now talk about retraction in two directions — one reads the
    value, one tells a person to write it — which is exactly the shape in which
    a Skill starts writing it.
    """
    text = read(path)
    assert "do not write either" in text.lower(), (
        f"{path} no longer says the Skill must not write `status: retracted` / "
        "`## Retraction Reason` itself."
    )


def test_fix_names_the_retraction_route_for_source_level_feedback():
    """The entry, not the guard (Issue #928).

    Issue #743 put "something is wrong with a source" into the tracking-Issue
    template, and `/wikicommit-fix <issue-url>` is what reads those comments —
    but the Skill had nothing to say about them, so Step 4's
    corroboration rule answered with "the feedback could not be corroborated in
    the source document": true, and a dead end rather than a route.
    """
    text = read(SKILLS / "wikicommit-fix" / "SKILL.md")
    assert "status: retracted" in text and "## Retraction Reason" in text, (
        "wikicommit-fix no longer names the retraction route, so feedback about "
        "a bad source lands on the corroboration rule and stops there."
    )


@pytest.mark.parametrize(
    "path, phrase",
    [
        pytest.param(CHECK_SCRIPT, "rewrites nothing", id="check-script-docstring"),
        pytest.param(DOCS / "DesignDoc-ScriptSpec.md", "条件付き", id="design-doc-scriptspec"),
    ],
)
def test_the_derivation_freshness_handoff_is_still_qualified(path, phrase):
    """`check_derivation_freshness.py` covers the indirect case only partly.

    The tempting one-liner — "a view page standing on a retracted source is
    `check_derivation_freshness.py`'s business" — is what both copies used to
    say, and it is wrong in a way that reads as settled: that script fires when
    a grounding page is *rewritten*, and a retraction rewrites nothing. So it
    reaches the case only after a human has already acted. Drop the
    qualification and the next reader concludes the case is covered.
    """
    assert phrase in read(path), (
        f"{path} no longer qualifies the handoff to check_derivation_freshness.py."
    )
