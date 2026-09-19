"""Tests for .wikicommit/scripts/check_review_coverage.py (Issue #750)"""

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / ".wikicommit" / "scripts"
SCRIPT = SCRIPTS / "check_review_coverage.py"
RECORDER = SCRIPTS / "record_review.py"

PAGE_REL = ".wikicommit/entity/ja/Person/yamada-taro.md"


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=cwd, check=False
    )


def record(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [sys.executable, str(RECORDER), *args],
        capture_output=True, text=True, cwd=cwd, input=stdin, check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


def write_page(root: Path, rel: str = PAGE_REL, *, body: str = "本文。",
               url: str = "https://example.com/a", src_hash: str = "sha256:cd34") -> Path:
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        'title: "T"\n'
        "lang: ja\n"
        'type: "schema:Person"\n'
        "review_status: pending\n"
        "sources:\n"
        "  - type: url\n"
        f"    url: {url}\n"
        f"    hash: {src_hash}\n"
        "---\n"
        "\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return page


def ai(cwd: Path, page: str = PAGE_REL, *, attempts: str = "1", result: str = "pass",
       model: str = "claude-opus-5[1m]", stdin: str | None = None) -> None:
    args = [page, "--kind", "ai", "--stage", "generate-pass4", "--model", model,
            "--attempts", attempts, "--result", result]
    if stdin is not None:
        args += ["--json", "-"]
    record(cwd, *args, stdin=stdin)


def test_no_review_tree_says_so_rather_than_reporting_zeros(tmp_path):
    """"Nothing recorded yet" and "everything came back zero" are different states."""
    write_page(tmp_path)
    out = run(tmp_path).stdout
    assert "SUMMARY: pages=0" in out
    assert "NOTE:" in out


def test_reports_coverage_per_model(tmp_path):
    write_page(tmp_path)
    write_page(tmp_path, ".wikicommit/entity/ja/Place/x.md")
    ai(tmp_path)
    ai(tmp_path, ".wikicommit/entity/ja/Place/x.md", model="other-model")
    out = run(tmp_path).stdout
    assert (
        "SUMMARY: pages=2, ai_reviewed=2, human_reviewed=0, human_notes=0,"
        " findings=0, models=2"
    ) in out
    assert "COVERAGE: claude-opus-5[1m] 1 pages, 0 findings, 0 pages with attempts>=2" in out
    assert "COVERAGE: other-model 1 pages" in out


def test_a_page_with_no_record_is_unreviewed(tmp_path):
    write_page(tmp_path)
    write_page(tmp_path, ".wikicommit/entity/ja/Place/x.md")
    ai(tmp_path)
    out = run(tmp_path).stdout
    assert "UNREVIEWED: .wikicommit/entity/ja/Place/x.md" in out
    assert "UNREVIEWED: " + PAGE_REL not in out


FINDING = ('{"result":"PASS","issues":[{"type":"HALLUCINATION","claim":"c",'
           '"instruction":"i","round":1}]}')


def test_retries_and_findings_make_a_page_risky(tmp_path):
    """RISKY is the sampling list — the thing that evaporated when verdicts were dropped."""
    write_page(tmp_path)
    ai(tmp_path, attempts="3", stdin=FINDING)
    out = run(tmp_path).stdout
    assert "RISKY: " + PAGE_REL + " (attempts=3, findings=1)" in out


def test_a_clean_first_pass_is_not_risky(tmp_path):
    write_page(tmp_path)
    ai(tmp_path)
    assert "RISKY:" not in run(tmp_path).stdout


def test_a_later_clean_review_takes_a_page_off_the_sampling_list(tmp_path):
    """Issue #760. Records are immutable and never deleted, so summing over the
    history meant a page that was ever retried stayed on `RISKY:` forever and the
    list converged on the whole wiki — at which point it selects nothing."""
    write_page(tmp_path)
    ai(tmp_path, attempts="3", stdin=FINDING)
    assert "RISKY: " + PAGE_REL in run(tmp_path).stdout

    ai(tmp_path)
    out = run(tmp_path).stdout
    assert "RISKY:" not in out
    # The history itself is untouched — only which record RISKY reads changed.
    assert "findings=1" in out.split("SUMMARY:")[1].split("\n")[0]


def test_the_standing_review_keeps_reporting_its_own_retries(tmp_path):
    """The "it took two rounds" signal is not lost: the standing record carries it."""
    write_page(tmp_path)
    ai(tmp_path)
    ai(tmp_path, attempts="2")
    assert "RISKY: " + PAGE_REL + " (attempts=2, findings=0)" in run(tmp_path).stdout


def test_a_human_finding_makes_a_page_risky(tmp_path):
    """`/wikicommit-review` can write findings too, so restricting the search to
    `kind: ai` would drop a human's finding on the floor."""
    write_page(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "human", "--stage", "review-skill",
           "--reviewer", "octocat", "--result", "fail", "--json", "-", stdin=FINDING)
    assert "RISKY: " + PAGE_REL + " (attempts=1, findings=1)" in run(tmp_path).stdout


def test_a_discarded_record_does_not_make_a_page_risky(tmp_path):
    """Issue #760 検討事項 2. A discarded verdict judged a draft that was thrown
    away, and for `action: update` it may name a source the page does not carry."""
    write_page(tmp_path)
    ai(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
           "--model", "m", "--attempts", "3", "--result", "discarded",
           "--json", "-", stdin=FINDING)
    assert "RISKY:" not in run(tmp_path).stdout


def test_stale_when_the_page_text_changed(tmp_path):
    """The /wikicommit-fix case: prose rewritten after the verdict was made."""
    write_page(tmp_path)
    ai(tmp_path)
    write_page(tmp_path, body="書き換えられた本文。")
    out = run(tmp_path).stdout
    assert "STALE_REVIEW: " + PAGE_REL in out
    assert "page content changed" in out


def test_stale_when_a_source_changed(tmp_path):
    """The case nothing else covers: check_ingest_freshness.py ignores url sources."""
    write_page(tmp_path)
    ai(tmp_path)
    write_page(tmp_path, src_hash="sha256:DIFFERENT")
    out = run(tmp_path).stdout
    assert "source changed: https://example.com/a" in out


def test_stale_when_a_source_was_removed_from_the_page(tmp_path):
    write_page(tmp_path)
    ai(tmp_path)
    write_page(tmp_path, url="https://example.com/b")
    out = run(tmp_path).stdout
    assert "source no longer on the page: https://example.com/a" in out


def test_bookkeeping_only_edits_do_not_go_stale(tmp_path):
    """Otherwise every merge would light the whole wiki up."""
    write_page(tmp_path)
    ai(tmp_path)
    page = tmp_path / PAGE_REL
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "review_status: pending", 'review_status: reviewed\nreviewed_by: "octocat"'
        ),
        encoding="utf-8",
    )
    assert "STALE_REVIEW:" not in run(tmp_path).stdout


def test_a_discarded_record_never_reports_page_staleness(tmp_path):
    """An empty hash means the page was never written, not that it diverged."""
    record(tmp_path, ".wikicommit/entity/ja/Place/gone.md", "--kind", "ai",
           "--stage", "generate-pass4", "--model", "m", "--result", "discarded")
    assert "STALE_REVIEW:" not in run(tmp_path).stdout


def test_a_discarded_update_does_not_make_the_page_it_left_alone_stale(tmp_path):
    """Pass 4 step 5 records `discarded` for an `action: update` entity as well, and
    there the pre-existing page stays on disk. `reviewed_sources` then comes from
    `--sources-from` (the source being ingested) rather than from the page, so it
    names a source the page has never carried — measuring the page against it would
    report `source no longer on the page` forever, and would also hide the earlier
    verdict that does still stand behind the page's text."""
    write_page(tmp_path)
    ai(tmp_path)

    mgmt = tmp_path / ".wikicommit/source/url/example.com/b.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/b\n"
        "  hash: sha256:ef56\nstatus: pending\n---\n",
        encoding="utf-8",
    )
    record(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
           "--model", "m", "--result", "discarded", "--sources-from", str(mgmt))

    out = run(tmp_path).stdout
    assert "STALE_REVIEW:" not in out
    assert "https://example.com/b" not in out

    # And the verdict that does stand behind the text keeps working.
    write_page(tmp_path, body="changed")
    assert "STALE_REVIEW: " + PAGE_REL in run(tmp_path).stdout


def test_a_page_whose_only_record_was_discarded_is_unreviewed(tmp_path):
    """Issue #766. Every per-page line skips a discarded record, so before this the
    page appeared in none of them while SUMMARY/COVERAGE counted it as reviewed."""
    write_page(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
           "--model", "m", "--attempts", "3", "--result", "discarded",
           "--json", "-", stdin=FINDING)
    out = run(tmp_path).stdout

    # It is named, and the line says which of the two unreviewed states it is.
    assert "UNREVIEWED: " + PAGE_REL in out
    assert "every one was discarded" in out

    # And it is no longer counted as covered.
    assert "ai_reviewed=0" in out
    assert "COVERAGE: m 0 pages, 0 findings, 0 pages with attempts>=2, 1 discarded" in out

    # `findings=` stays cumulative over the whole history (Issue #760; out of
    # scope for #766), so the discarded review's finding is still tallied.
    assert "findings=1," in out


def test_a_page_with_no_record_at_all_is_not_annotated(tmp_path):
    """The annotation exists to tell the two unreviewed states apart, so the
    ordinary one must not carry it."""
    write_page(tmp_path)
    write_page(tmp_path, ".wikicommit/entity/ja/Place/x.md")
    ai(tmp_path)
    lines = run(tmp_path).stdout.splitlines()
    unreviewed = [line for line in lines if line.startswith("UNREVIEWED:")]
    assert unreviewed == ["UNREVIEWED: .wikicommit/entity/ja/Place/x.md"]


def test_a_record_without_a_hash_is_not_called_discarded(tmp_path):
    """Issue #766. A record is non-standing when it carries no `page_content_hash`,
    which is not the same claim as "it was discarded" — this tree is meant to be
    hand-writable (Issue #750), and a hand-written record simply has no hash. Saying
    it was discarded sends the reader looking for a discarded review that never was."""
    write_page(tmp_path)
    directory = tmp_path / ".wikicommit/review/entity/ja/Person/yamada-taro"
    directory.mkdir(parents=True)
    (directory / "20260905-101010-human.md").write_text(
        "---\n"
        f"page: {PAGE_REL}\n"
        "kind: human\n"
        "stage: review-skill\n"
        "reviewer: octocat\n"
        'reviewed_at: "2026-09-05"\n'
        "result: pass\n"
        "findings: []\n"
        "---\n\n読んだ。\n",
        encoding="utf-8",
    )
    out = run(tmp_path).stdout

    assert "UNREVIEWED: " + PAGE_REL in out
    assert "every one was discarded" not in out
    assert "none carries a page_content_hash" in out


def test_a_discarded_attempt_after_a_clean_pass_keeps_the_standing_verdict(tmp_path):
    """The `action: update` case: the page on disk is still the one the earlier
    review passed, so it stays covered — but the thrown-away attempt is reported
    rather than folded into the coverage numbers."""
    write_page(tmp_path)
    ai(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
           "--model", "claude-opus-5[1m]", "--attempts", "3", "--result", "discarded",
           "--json", "-", stdin=FINDING)
    out = run(tmp_path).stdout

    assert "UNREVIEWED:" not in out
    assert "ai_reviewed=1" in out
    # The standing verdict was a clean single-attempt pass, so no phantom retry.
    assert "COVERAGE: claude-opus-5[1m] 1 pages, 0 findings, 0 pages with attempts>=2, 1 discarded" in out
    assert "RISKY:" not in out


def test_human_reviews_are_counted(tmp_path):
    """The main human path is the workflow; a coverage number missing it is worse than none."""
    write_page(tmp_path)
    ai(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "human", "--stage", "issue-close",
           "--reviewer", "octocat", "--result", "pass")
    assert "human_reviewed=1" in run(tmp_path).stdout


def test_retracted_evidence_is_distinct_from_check_retracted_sources(tmp_path):
    """Only a record can say the verdict actually rested on the withdrawn source."""
    write_page(tmp_path)
    ai(tmp_path)
    mgmt = tmp_path / ".wikicommit/source/url/example.com/a.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\n  hash: sha256:cd34\n"
        "status: retracted\n---\n",
        encoding="utf-8",
    )
    out = run(tmp_path).stdout
    assert "RETRACTED_EVIDENCE: " + PAGE_REL in out
    assert "since retracted" in out


def test_removed_pages_are_not_counted(tmp_path):
    page = write_page(tmp_path)
    page.write_text(
        page.read_text(encoding="utf-8").replace("lang: ja", "lang: ja\nstatus: removed"),
        encoding="utf-8",
    )
    (tmp_path / ".wikicommit" / "review").mkdir(parents=True, exist_ok=True)
    assert "SUMMARY: pages=0" in run(tmp_path).stdout


def test_exit_code_is_always_zero(tmp_path):
    write_page(tmp_path)
    ai(tmp_path)
    write_page(tmp_path, body="changed")
    assert run(tmp_path).returncode == 0


# --- `--discarded-reason` (Issue #969) ---------------------------------------
#
# `/wikicommit-merge` Step 9's only other source of a failure reason is deleted
# on Pass 4's `partial` branch, and `partial` is the ordinary shape of a
# generation failure — so without this mode the reason reads `unknown` on the
# tracking Issues that step creates most often.


def reason(cwd: Path, *pages: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--discarded-reason", *pages],
        capture_output=True, text=True, cwd=cwd, check=False,
    )


DISCARD_FINDING = (
    '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","round":1,'
    '"source_file":".wikicommit/.cache/ingest-fetch/arxiv.org/x.md",'
    '"source_lines":"160-166","claim":"c",'
    '"instruction":"The source only cites it in passing."}]}'
)


def discard(cwd: Path, page: str = PAGE_REL, *, stdin: str = DISCARD_FINDING,
            attempts: str = "1") -> None:
    """Record a page that Pass 4 threw away, the way Pass 4 step 5 does."""
    record(cwd, page, "--kind", "ai", "--stage", "generate-pass4", "--model", "m",
           "--attempts", attempts, "--result", "discarded", "--json", "-", stdin=stdin)


def test_discarded_reason_reports_the_finding(tmp_path):
    write_page(tmp_path)
    discard(tmp_path)
    out = reason(tmp_path, PAGE_REL).stdout
    assert f"REASON: {PAGE_REL}" in out
    assert "MISSING_SOURCE" in out
    assert "The source only cites it in passing." in out
    assert "SUMMARY: pages=1, with_reason=1" in out


def test_discarded_reason_never_prints_the_cache_path(tmp_path):
    """`source_file` points into `.wikicommit/.cache/`, which is gitignored and
    machine-local — it names nothing in another clone or after a cache clear."""
    write_page(tmp_path)
    discard(tmp_path)
    out = reason(tmp_path, PAGE_REL).stdout
    assert ".wikicommit/.cache/" not in out
    # But which *kind* of file the line numbers count into is still said.
    assert "of the extracted source text" in out


def test_discarded_reason_labels_a_page_source_differently(tmp_path):
    """Issue #566's discriminator: a path inside the entity tree is another page."""
    write_page(tmp_path)
    discard(tmp_path, stdin=(
        '{"result":"FAIL","issues":[{"type":"CONTRADICTION","round":1,'
        '"source_file":".wikicommit/entity/ja/Place/other.md",'
        '"source_lines":"L10-L12","instruction":"Conflicts."}]}'
    ))
    out = reason(tmp_path, PAGE_REL).stdout
    assert "of another page" in out
    assert "of the extracted source text" not in out


def test_discarded_reason_says_no_record_rather_than_unknown(tmp_path):
    """A failure predating the record tree has nothing to show; saying so is
    different from saying the reason is unknowable."""
    write_page(tmp_path)
    ai(tmp_path)  # a passing record exists, but nothing was discarded
    out = reason(tmp_path, PAGE_REL, ".wikicommit/entity/ja/Place/never.md").stdout
    assert f"NO_RECORD: {PAGE_REL}" in out
    assert "NO_RECORD: .wikicommit/entity/ja/Place/never.md" in out
    assert "unknown" not in out
    assert "SUMMARY: pages=2, with_reason=0" in out


def test_discarded_reason_takes_the_newest_discard(tmp_path):
    """Newest by `record_sort_key()`, which is what the writer numbers with —
    plain filename order would hand back the oldest record of a same-second pair."""
    write_page(tmp_path)
    discard(tmp_path, stdin=(
        '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","round":1,'
        '"instruction":"older reason"}]}'
    ))
    discard(tmp_path, stdin=(
        '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","round":1,'
        '"instruction":"newer reason"}]}'
    ))
    out = reason(tmp_path, PAGE_REL).stdout
    assert "newer reason" in out
    assert "older reason" not in out


def test_discarded_reason_flattens_a_multiline_instruction(tmp_path):
    """Each finding is one line; an embedded newline would split it in two."""
    write_page(tmp_path)
    discard(tmp_path, stdin=(
        '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","round":1,'
        '"instruction":"first line\\nsecond line"}]}'
    ))
    out = reason(tmp_path, PAGE_REL).stdout
    assert "first line second line" in out


def test_discarded_reason_exits_zero_with_no_review_tree(tmp_path):
    """The default mode's `REVIEW_DIR` guard must not swallow this one: a
    repository with no records still has to answer, and `NO_RECORD:` is that
    answer rather than an error."""
    write_page(tmp_path)
    result = reason(tmp_path, PAGE_REL)
    assert result.returncode == 0, result.stderr
    assert f"NO_RECORD: {PAGE_REL}" in result.stdout


def test_discarded_reason_numbers_the_rounds_when_there_is_more_than_one(tmp_path):
    """A discarded record flattens every round together (Issue #571: each round can
    raise a different defect), so an unnumbered list reads as simultaneous problems."""
    write_page(tmp_path)
    discard(tmp_path, attempts="2", stdin=(
        '{"result":"FAIL","issues":['
        '{"type":"MISSING_SOURCE","round":1,"instruction":"drop the date"},'
        '{"type":"HALLUCINATION","round":2,"instruction":"drop the affiliation"}]}'
    ))
    out = reason(tmp_path, PAGE_REL).stdout
    assert "round 1 MISSING_SOURCE" in out
    assert "round 2 HALLUCINATION" in out
    # A single-round record stays as short as it was.
    other = ".wikicommit/entity/ja/Person/other.md"
    write_page(tmp_path, other)
    discard(tmp_path, other)
    assert "round 1 MISSING_SOURCE" not in reason(tmp_path, other).stdout


def test_discarded_reason_rejects_a_path_outside_the_page_trees(tmp_path):
    """`record_dir_for()` strips `.wikicommit/` by length, so an unexpected path
    resolves to a silently wrong directory — and a short one raises. Neither may
    come back as `NO_RECORD:`, which Step 9 writes into an Issue as a real answer."""
    write_page(tmp_path)
    result = reason(tmp_path, ".wikicommit/source/url/example.com/a.md", "foo.md")
    assert result.returncode == 0, result.stderr
    assert "ERROR: .wikicommit/source/url/example.com/a.md" in result.stdout
    assert "ERROR: foo.md" in result.stdout
    assert "NO_RECORD:" not in result.stdout
    assert "SUMMARY: pages=2, with_reason=0" in result.stdout


def test_discarded_reason_accepts_zero_pages(tmp_path):
    """Step 9's second target is a source caught in Pass 1, whose `failed_pages` is
    empty (Issue #910) — the caller's expansion then leaves the flag with no values,
    and a usage error there breaks the always-0 contract."""
    result = reason(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "SUMMARY: pages=0, with_reason=0" in result.stdout


# --- `human_notes` (Issue #952) ----------------------------------------------
#
# Closing a tracking Issue with no comment is a legitimate close (Issue #762),
# and every other output — the banner, `reviewed_by`, `human_reviewed`, the
# published overview — looks identical whether the note came or not. This number
# is the only place the difference shows.


def human(cwd: Path, page: str = PAGE_REL, *, note: str | None = None,
          stage: str = "issue-close") -> None:
    args = [page, "--kind", "human", "--stage", stage, "--reviewer", "octocat",
            "--result", "pass"]
    if note is not None:
        args += ["--note", note]
    record(cwd, *args)


def test_a_human_record_with_a_note_is_counted(tmp_path):
    write_page(tmp_path)
    human(tmp_path, note="I had not realized the guard was non-blocking.")
    out = run(tmp_path).stdout
    assert "human_reviewed=1" in out
    assert "human_notes=1" in out


def test_a_human_record_without_a_note_is_not_counted(tmp_path):
    """Not a defect — closing in silence is a legitimate close. It is simply the
    thing no other output distinguishes."""
    write_page(tmp_path)
    human(tmp_path)
    out = run(tmp_path).stdout
    assert "human_reviewed=1" in out
    assert "human_notes=0" in out


def test_an_ai_record_body_is_not_counted_as_a_note(tmp_path):
    """A `kind: ai` body holds Pass 4's non-blocking observations (Issue #834),
    which are not a trace of a person having read the page. Counting both would
    make one number stand for two different things."""
    write_page(tmp_path)
    record(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
           "--model", "m", "--result", "pass", "--note", "featureList reads thin.")
    out = run(tmp_path).stdout
    assert "ai_reviewed=1" in out
    assert "human_notes=0" in out


def test_the_key_is_present_even_with_no_review_tree(tmp_path):
    """A key that appears on only one of the two exits cannot be read: 0 and
    "this build does not have it" would look the same."""
    write_page(tmp_path)
    assert "human_notes=0" in run(tmp_path).stdout
