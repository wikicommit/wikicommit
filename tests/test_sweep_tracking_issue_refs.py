"""Tests for dev/scripts/sweep_tracking_issue_refs.py

The script under test is dev-only (`dev/` is permanently excluded from the
published snapshot), so every test here is skipped there, following the same
pattern as `tests/test_check_issue_registration.py` (Issue #788).

What is actually being pinned is the pair of invariants the sweep rests on: a
bullet's leading reference must stay bare (it is the entry itself, and what
GitHub's tracking relationship attaches to), and an already-wrapped reference
must not be wrapped again (so repeated runs converge). Both are silent when
broken -- the body still renders, it just stops showing the states the sweep
exists to preserve (Issue #805).

The third invariant is louder but worse: anything that is not a bare `#NNN` of
this repository has to survive byte for byte. The sweep edits the live Issue in
place, so rewriting half of a Markdown link, or a `#123` that is really a URL
fragment, corrupts a 65,000-character body with no copy to restore from.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from _publication import is_development_repository

SCRIPT = Path(__file__).parent.parent / "dev" / "scripts" / "sweep_tracking_issue_refs.py"

pytestmark = pytest.mark.skipif(
    not is_development_repository(),
    reason="published snapshot: dev/scripts/sweep_tracking_issue_refs.py is intentionally not published",
)

STATES = {543: "OPEN", 549: "CLOSED", 577: "CLOSED", 600: "OPEN", 700: "MERGED"}


def load_sweep():
    spec = importlib.util.spec_from_file_location("sweep_tracking_issue_refs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.sweep


def test_the_script_under_test_exists():
    assert SCRIPT.is_file()


def test_leading_reference_stays_bare_even_when_closed():
    sweep = load_sweep()
    out, _, _ = sweep("- #549 done already", STATES)
    assert out == "- #549 done already"


def test_closed_prerequisite_is_wrapped_and_open_one_is_not():
    sweep = load_sweep()
    out, delinked, _ = sweep("- #600 title（p3-221・← #549 / #600）", STATES)
    assert out == "- #600 title（p3-221・← `#549` / #600）"
    assert delinked == 1


def test_merged_pull_request_counts_as_closed():
    sweep = load_sweep()
    out, delinked, _ = sweep("- #600 title（← #700）", STATES)
    assert out == "- #600 title（← `#700`）"
    assert delinked == 1


def test_markdown_links_are_normalized_to_bare_references():
    sweep = load_sweep()
    line = "- [#600](https://github.com/o/r/issues/600) t（← [#549](https://github.com/o/r/issues/549)）"
    out, delinked, normalized = sweep(line, STATES, "o/r")
    assert out == "- #600 t（← `#549`）"
    assert (delinked, normalized) == (1, 1)


def test_pull_request_self_links_are_normalized_too():
    sweep = load_sweep()
    out, delinked, _ = sweep("- #600 t（← [#700](https://github.com/o/r/pull/700)）", STATES, "o/r")
    assert out == "- #600 t（← `#700`）"
    assert delinked == 1


def test_link_to_another_repository_is_left_alone():
    # Normalizing it to a bare `#549` would silently re-point it at this repo.
    sweep = load_sweep()
    line = "- #600 t（← [#549](https://github.com/other/repo/issues/549)）"
    out, delinked, normalized = sweep(line, STATES, "o/r")
    assert out == line
    assert (delinked, normalized) == (0, 0)


def test_link_whose_text_is_not_just_the_number_is_left_alone():
    # Half-rewriting this used to drop the opening bracket and eat the URL.
    sweep = load_sweep()
    line = "- #600 t（← [レビュー #549](https://github.com/o/r/issues/549)）"
    out, delinked, normalized = sweep(line, STATES, "o/r")
    assert out == line
    assert (delinked, normalized) == (0, 0)


def test_link_to_a_non_github_url_is_left_alone():
    sweep = load_sweep()
    line = "- #600 t（← [#549](https://example.com/x)）"
    out, delinked, normalized = sweep(line, STATES, "o/r")
    assert out == line
    assert (delinked, normalized) == (0, 0)


def test_url_fragments_are_not_references():
    sweep = load_sweep()
    line = "- #600 see https://example.com/page#549 and docs/DesignDoc-data.md#549 too"
    out, delinked, _ = sweep(line, STATES, "o/r")
    assert out == line
    assert delinked == 0


def test_double_backtick_code_spans_are_left_alone():
    sweep = load_sweep()
    line = "- #600 ``#549`` stays as it is"
    out, delinked, _ = sweep(line, STATES, "o/r")
    assert out == line
    assert delinked == 0


def test_existing_code_spans_are_left_alone():
    sweep = load_sweep()
    line = "- #600 `#549` に触れる文（p3.1-077・← `#577`）"
    out, delinked, _ = sweep(line, STATES)
    assert out == line
    assert delinked == 0


def test_task_list_checkboxes_are_still_recognized():
    sweep = load_sweep()
    out, delinked, _ = sweep("- [x] #600 title（← #549）", STATES)
    assert out == "- [x] #600 title（← `#549`）"
    assert delinked == 1


def test_prose_lines_are_untouched():
    sweep = load_sweep()
    prose = "第7波（#549〜#600）: 本文の散文は対象外であり、#577 もそのまま残す。"
    out, delinked, normalized = sweep(prose, STATES)
    assert out == prose
    assert (delinked, normalized) == (0, 0)


def test_sweep_is_idempotent():
    sweep = load_sweep()
    body = "- #600 title（← #549 / #700 / #600）\n\n散文の #549 は対象外。\n- [ ] #543 x（← #577）"
    once, delinked, _ = sweep(body, STATES)
    twice, again, normalized = sweep(once, STATES)
    assert delinked == 3
    assert twice == once
    assert (again, normalized) == (0, 0)
