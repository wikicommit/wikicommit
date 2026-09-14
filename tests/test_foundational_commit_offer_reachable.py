"""The foundational-commit offer has to stay reachable on the Quartz path (#865).

Issue #843 had the agent offer to run `/wikicommit-init`'s foundational commit,
and the offer carried three conditions under which it is withheld. One of them —
"the printed list still has a `Set up Quartz v5` step above the commit step" —
holds on *every* first `--quartz`/`--quartz-pages` run, because
`check_quartz_setup.py` can only report Quartz as fully set up once `quartz/`
exists, and on a first run it does not. Re-running `/wikicommit-init` afterwards
did not reach the offer either, because a second condition read "this run did not
write the `.gitignore`" and `.gitignore` carries `update="review"` in
`_root_outputs.py` — so every re-init logged `SKIPPED: .gitignore (already
exists)` and that condition fired. The offer was therefore unreachable for every
Quartz user, which is the population the printed guidance is mostly for.

Issue #865 made that third case a *deferral*: the agent asks the user to finish
Quartz setup, re-checks the status, reprints the guidance, and makes the offer
against the reprint.

**Issue #873 removed the other half of the dead end**, so re-running
`/wikicommit-init` now does reach the offer: the `.gitignore` condition asks what
is *in* the file (`GITIGNORE_READY:`) rather than who wrote it, and a repository
WikiCommit made itself keeps answering yes. The deferral stays anyway, and the
test below pins the reason it stays — finishing Quartz setup and coming back
inside one session is a single continuous action, where a re-run is a second
invocation the user has to think to make.

Two halves are pinned here, and they fail differently:

- **The route is prose.** Nothing executes it, so an edit that collapses the
  deferral back into a skip breaks no other test — and the symptom is silence
  (the offer simply never comes), exactly the failure mode Issue #865 reports.
- **The reprint genuinely moves the commit step.** That part *is* mechanical, and
  it is the premise the prose rests on: if `print_next_steps.py` ever kept the
  setup step above the commit step regardless of the status flags, the deferral
  would resolve into the same dead end it was written to escape.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INIT_SKILL = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "SKILL.md"
PRINT_NEXT_STEPS = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "print_next_steps.py"
)

_COMMIT_STEP_MARKER = "Commit the generated foundational files"
_QUARTZ_STEP_MARKER = "Set up Quartz v5"


def _numbered_steps(*flags: str) -> list[str]:
    """The guidance's numbered step headings, in order."""
    result = subprocess.run(
        [sys.executable, str(PRINT_NEXT_STEPS), *flags],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    )
    return [line for line in result.stdout.splitlines() if line[:1].isdigit() and ". " in line[:4]]


def _index_of(steps: list[str], marker: str) -> int | None:
    for i, line in enumerate(steps):
        if marker in line:
            return i
    return None


def test_the_quartz_case_is_deferred_rather_than_skipped():
    """Whatever the wording, the Skill must not say this case ends the offer.

    Checked as a pair — the presence of "deferred" and the absence of the
    previous "skip the offer in any of the three cases" framing — because either
    one alone could be satisfied by a half-edit that leaves the behaviour at the
    dead end.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "deferred rather than skipped" in text, (
        "wikicommit-init/SKILL.md no longer marks the pending-Quartz case as deferred; "
        "if it is skipped outright the offer is unreachable on every first --quartz run (#865)"
    )
    assert "in any of the three cases below" not in text, (
        "SKILL.md still presents three skip cases; the pending-Quartz case is a deferral, "
        "so counting it among them restores the dead end Issue #865 removed"
    )


def test_the_skill_states_why_the_deferral_survives_the_gitignore_fix():
    """The motive for the deferral, restated after its original one was removed.

    Issue #865's argument was that a re-run could not reach the offer either, so
    deferring was the only route. Issue #873 made a re-run reach it, which takes
    that argument away and leaves the deferral looking like a courtesy a later
    reader would simplify out. The reason it survives is a different one and has
    to be on the page: the deferral completes inside the session the user is
    already in.

    Pinned as a pair, because the stale half is the dangerous one — a SKILL.md
    that still claims a re-run trips the `.gitignore` case would send someone to
    re-derive a condition that no longer exists.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "Keep waiting here rather than sending the user away to re-run" in text, (
        "SKILL.md no longer says why the Quartz deferral is kept now that a re-init reaches "
        "the offer (#873); without a motive it reads as removable (#865)"
    )
    assert "not reach it either, because `init.py` then logs" not in text, (
        "SKILL.md still claims re-running /wikicommit-init trips the .gitignore case. "
        "Issue #873 moved that condition onto the file's contents, so a repository "
        "WikiCommit made itself now answers GITIGNORE_READY: yes"
    )
    assert "Issue #865" in text


def test_the_gitignore_condition_reads_the_contents_rather_than_the_log():
    """The condition Issue #873 replaced, pinned so it cannot drift back.

    Keying on `SKIPPED: .gitignore (already exists)` is the tempting shape — it is
    one grep of output already on screen — and it is wrong for the case that
    matters most in practice: `.gitignore` is `always_skip_existing`, so that line
    appears on **every** re-init, including in repositories WikiCommit created,
    where `git add -A` is exactly as safe as it was the first time.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "GITIGNORE_READY: no" in text, (
        "SKILL.md no longer reads init.py's GITIGNORE_READY: line; the condition is about "
        "what the .gitignore contains, and init.py has already answered it (#873)"
    )
    assert "Do not key this on `SKIPPED: .gitignore (already exists)`" in text, (
        "SKILL.md no longer warns against the old condition. It is the shape someone "
        "reaches for again, and it stops the offer on every re-init (#873)"
    )


def test_the_skill_does_not_have_the_agent_add_the_submodule():
    """`git submodule add` stays with the user (Issue #843 item 5).

    The deferral brings the agent into the same breath as that command, so the
    boundary is worth pinning: a structural change to the repository with its own
    failure and recovery is out of scope here, not settled by the commit offer.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "**you do not run them**" in text


def test_the_deferral_excludes_the_pre_existing_package_json_case():
    """`--package-json-skipped` ends the offer instead of deferring it.

    Two reasons, either one sufficient: re-running `check_quartz_setup.py` would
    run the `npm install` step 3.d deliberately refuses to run against a
    repository's own `package.json` (Issue #276), and `print_next_steps.py` keeps
    the setup step under that flag whatever the status says — so the reprint can
    never drop it and the deferral would have nothing to resolve into.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "--package-json-skipped" in text
    assert "ends this case rather than deferring it" in text, (
        "SKILL.md no longer carves --package-json-skipped out of the deferral; there the "
        "re-check runs npm install on a pre-existing package.json and the reprint keeps the "
        "setup step regardless of status, so the deferral cannot resolve (#865 / #276)"
    )
    # The premise the reprint step used to assert unconditionally.
    assert "step is now gone from that output and the commit step is first" not in text, (
        "SKILL.md asserts the reprint always drops the setup step and leads with the commit; "
        "two reachable statuses keep a step above it (--package-json-skipped, and a failed "
        "install-plugins attempt)"
    )


def test_a_later_does_not_spend_the_deferral():
    """The pilot's order answers the Quartz ask with "later" and resumes after.

    `dev/`'s round6 walkthrough puts the policy files between `/wikicommit-init`
    and the Quartz step, so "later" is the expected answer rather than a decline;
    if SKILL.md treats it as ending the offer, reporting completion afterwards has
    no handler and the commit goes back to being done by hand.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "the hold is not spent" in text, (
        "SKILL.md treats a 'later' as ending the Quartz deferral; the documented pilot order "
        "relies on reporting completion after intervening steps (#865)"
    )


def test_the_reprint_puts_the_commit_step_ahead_of_quartz_setup():
    """The mechanical premise under the prose, checked on both sides of the step.

    Before: the setup step precedes the commit step, which is the condition that
    holds the offer back. After a status saying Quartz is set up: the setup step
    is gone entirely, so the offer applies to the reprint.
    """
    common = [
        "--variant", "quartz_pages",
        "--lychee-installed", "--markitdown-installed",
        "--actions-pr-permission-enabled",
    ]

    before = _numbered_steps(*common, "--quartz-status", "npm_install_completed_submodule_pending")
    quartz_at = _index_of(before, _QUARTZ_STEP_MARKER)
    commit_at = _index_of(before, _COMMIT_STEP_MARKER)
    assert quartz_at is not None and commit_at is not None
    assert quartz_at < commit_at, "the condition Issue #865 defers on no longer arises"

    after = _numbered_steps(
        *common, "--quartz-status", "fully_set_up", "--install-plugins-status", "ok"
    )
    assert _index_of(after, _QUARTZ_STEP_MARKER) is None, (
        "the reprint still carries a Set up Quartz v5 step, so the deferral resolves into "
        "the same dead end it was written to escape (#865)"
    )
    assert _index_of(after, _COMMIT_STEP_MARKER) is not None


def test_the_skill_withholds_the_offer_when_wiki_work_is_pending():
    """The guard the widened `.gitignore` condition needs.

    Issue #873 made a re-init reach the offer in a repository WikiCommit made itself. By then
    `.wikicommit/entity/` / `.wikicommit/view/` / `.wikicommit/source/` can hold pages
    `/wikicommit-generate` wrote and `/wikicommit-merge` has not taken yet — tracked paths, so
    no `.gitignore` entry keeps `git add -A` off them, and `GITIGNORE_READY:` says nothing
    about them. Sweeping them in puts LLM-authored pages on the current branch with no PR,
    which is precisely the premise the offer's justification rests on being false.
    """
    text = INIT_SKILL.read_text(encoding="utf-8")
    assert "The working tree already has uncommitted wiki pages in it" in text, (
        "SKILL.md no longer withholds the offer when .wikicommit/entity|view|source has "
        "uncommitted pages; a re-init would commit generated pages outside /wikicommit-merge"
    )
    # Both halves of the detection command, pinned separately because dropping either one
    # breaks the guard in opposite directions and neither failure is visible in the prose.
    assert "'.wikicommit/entity/**/*.md'" in text, (
        "SKILL.md no longer scopes the pending-work check to *.md. A first init leaves those "
        "three trees holding only .gitkeep, so a directory-level check reports "
        "`?? .wikicommit/entity/` and withholds the offer on every first run — the case the "
        "offer exists for (#843)"
    )
    assert "git status --porcelain -uall" in text, (
        "SKILL.md no longer passes -uall. Without it git collapses an untracked directory "
        "into one `?? dir/` line that the *.md pathspec does not match, so a new page under "
        "a new Type directory goes unseen — the case this condition exists for"
    )
