"""Non-interactive runs defer human judgments rather than discarding them (Issue #910).

The failure this guards against is quiet by construction. A subagent-driven run is
non-interactive by definition, so every prompt in `wikicommit-generate` resolves
without a person — and before this, two of them resolved by throwing the source
away: guard A marked it `status: failed`, and a Pass 2b candidate below the strict
bar was declined so the entity was written under an ancestor type with no Skill able
to reclassify it afterwards. Neither left a report. `status: failed` is collected by
nothing (Pass 1 skips it, `check_ingest_freshness.py` skips it) and
`wikicommit-merge`'s generation-failure Issue keyed on `failed_pages`, which is empty
when the failure happened before any page was attempted.

So the assertions are about wording in instruction files, which is unusual — but the
behaviour lives only in that wording, and the saitama pilot measured guard A at 4
false positives in 8 genuine sources. A 30-source batch silently losing a third of
itself is what a regression here costs.

**One of these rules has since been redefined rather than regressed** (Issue #945):
`wikicommit-merge` no longer aborts when warnings remain and no one is there to
answer. That is the same principle applied to a case where the facts were different —
see `test_merge_records_warnings_rather_than_aborting_on_them` for which half moved
and which did not. When an assertion here starts failing, check that distinction
before assuming a regression: the question is not "did the wording change" but
"does the absence of an answer still cost the batch".
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
SKILLS = REPO / ".claude" / "skills"

sys.path.insert(0, str(REPO / "tools"))
from check_skill_md_lines import instruction_files  # noqa: E402


def _instructions(skill: str) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8") for p in instruction_files(SKILLS / skill)
    )


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_guard_a_defers_instead_of_failing_the_source():
    """The single highest-cost branch: a text-shape heuristic with a measured 50%
    false-positive rate deciding, unreviewed, to drop a source out of every queue."""
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass1-extract.md").read_text(encoding="utf-8"))
    marker = "**defer this source — do not mark it `status: failed`**"
    assert _flat(marker) in text, (
        "guard A's non-interactive branch no longer says to defer; if it marks the "
        "source failed again, nothing collects or reports it (Issue #910)"
    )
    assert "## Deferred Reason" in text, (
        "guard A defers without recording why, so the wait lives only in the output "
        "of the run that made it"
    )


def test_guard_b_and_empty_extraction_still_fail():
    """The other half of the rule, and the one a later edit is likelier to erode.

    Deferral is for judgments a person would answer differently. A known JS-shell
    domain and an unreadable file are not those: the verdict does not change with a
    human in the room, so deferring them would park sources in the queue that every
    future run would park again.
    """
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass1-extract.md").read_text(encoding="utf-8"))
    assert _flat("`status: failed` (extraction error)") in text, (
        "the empty/unreadable extraction case no longer fails the source; that one is "
        "deterministic and deferring it would queue a source nothing can resolve"
    )


def test_pass_2b_below_the_bar_defers_rather_than_declining():
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass2b-type.md").read_text(encoding="utf-8"))
    assert _flat("**defer this source** (Issue #910)") in text, (
        "a Pass 2b candidate below the strict bar is being declined again, so the "
        "entity is written under an ancestor type and nothing can reclassify it"
    )
    assert _flat("**Deferring is not persisting the candidate**") in text, (
        "the line separating deferral from the persisted `better_type_candidate` "
        "Issue #315 removed is gone; without it the two read as the same thing"
    )


def test_the_strict_auto_approval_path_is_untouched():
    """Issue #507's bar is what makes an unattended approval defensible; deferral was
    added underneath it, not in place of it."""
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass2b-type.md").read_text(encoding="utf-8"))
    assert _flat("treat as **approved without ever showing the prompt** (default **Y**)") in text


def test_an_ambiguous_entity_is_recorded_on_the_management_file():
    """The one deferral that cannot be expressed by leaving `status` alone.

    The source really did produce pages, so it moves to `partial` regardless. Without
    the field, `partial` with an empty `failed_pages` means both "excluded as
    off-theme" (which re-running reproduces forever) and "waiting on a human" (which
    a human can resolve), and the collection condition reads exactly that pair.
    """
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass4-review.md").read_text(encoding="utf-8"))
    assert "ambiguous_entities" in text
    assert _flat("remove the field entirely on any of the three branches above") in text, (
        "nothing clears `ambiguous_entities`, so a resolved source keeps claiming it "
        "is waiting on someone who has already been"
    )


def test_the_ambiguity_route_is_reconcile_not_a_collection_change():
    """Collecting it would rebuild the starvation Issue #567 removed: the same source
    read again returns the same ambiguity, every run, until a person happens to look."""
    text = _flat((SKILLS / "wikicommit-generate" / "references"
                  / "pass1-extract.md").read_text(encoding="utf-8"))
    assert _flat("**It deliberately does not collect them anyway.**") in text
    assert "/wikicommit-reconcile" in text, (
        "the collection step names no route out of an ambiguity, which is the gap "
        "Issue #910 set out to close"
    )


def test_the_two_undefined_generate_prompts_now_have_a_non_interactive_rule():
    """Not deferrals — places where the absence of an answer was simply unwritten.

    There were three of these under Issue #910; the third (`wikicommit-merge`
    Step 3) moved to its own test when Issue #945 redefined it, so the count in
    this name is two. Keep the name honest about what is asserted here — these
    names are the only record of which prompts are covered."""
    generate = _flat(_instructions("wikicommit-generate"))

    assert _flat("**In a non-interactive run, where no answer will arrive, register nothing"
                 " and report it** (Issue #910)") in generate, (
        "Step 0's policy conflict has no non-interactive rule again, so silence can "
        "be read as consent to register a source the policy argues against"
    )
    assert _flat("**In a non-interactive run, take (b) without asking**") in generate, (
        "the 5-source cap has no non-interactive rule again"
    )


def test_merge_records_warnings_rather_than_aborting_on_them():
    """The third of those prompts, redefined by Issue #945.

    This assertion used to require the opposite sentence — "abort — and say that is
    why" — and it is worth being exact about which half of Issue #910 moved. The
    principle did not: an unattended run still must not resolve a human judgment by
    pretending one was made. What moved is which resolution defers. Aborting is the
    deferring answer only while the working tree survives to be picked up later, and
    for this Skill it does not: nothing is committed at that point, and an unattended
    run's tree is gone when the session ends. So aborting *discarded* the batch, which
    is the behaviour the rest of this file exists to prevent.

    Two things keep that from being a loosening. Warnings never decided mergeability
    — every warning this step can produce is classified always-mergeable, so the
    confirmation was carrying a report to a person, not a verdict — and the report is
    not dropped, it moves to the PR body. Blocking findings are asserted separately
    below precisely because *they* are the half that must still stop the run."""
    merge = _flat(_instructions("wikicommit-merge"))

    assert _flat("**In a non-interactive run, where no answer will arrive, do not abort"
                 " — record the warnings and proceed** (Issue #945") in merge, (
        "wikicommit-merge aborts on warnings again with no one to ask, which throws "
        "away an unattended batch that had already passed every blocking check"
    )
    assert _flat("**Blocking is untouched.** `ERROR:` and `DUPLICATE:` still abort") in merge, (
        "the warning rule above is only safe while blocking still stops the run; "
        "without this sentence the two read as one relaxation"
    )
    assert _flat("Carry the warning list forward to Step 6") in merge, (
        "warnings are no longer confirmed with anyone, so if they also stop reaching "
        "the PR body they are simply lost"
    )


def test_merge_raises_a_tracking_issue_for_a_pass_1_failure():
    """`failed_pages` is written by Pass 4, so keying only on it missed every failure
    that happened before a page was attempted — while `wikicommit-status` excluded
    those same sources *because* this Issue was supposed to exist."""
    merge = (SKILLS / "wikicommit-merge" / "SKILL.md").read_text(encoding="utf-8")
    assert "elif fm.get('status') == 'failed':" in merge, (
        "Step 9's scan is back to `failed_pages` alone, so a source that failed in "
        "Pass 1 raises no tracking Issue and is excluded from wikicommit-status too"
    )


def test_status_counts_deferrals_and_failures_separately():
    status = _flat((SKILLS / "wikicommit-status" / "SKILL.md").read_text(encoding="utf-8"))
    assert "## Deferred Reason" in status, "nothing counts deferred sources between runs"
    assert "ambiguous_entities" in status, "nothing counts entities waiting on a type"
    assert _flat("**This is a column on the same line, not a line of its own**") in status, (
        "the deferral count became its own report line; it is a subset of the pending "
        "counts, so that reports the same number twice (Issue #864's shape)"
    )
