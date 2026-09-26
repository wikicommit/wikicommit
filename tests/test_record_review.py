"""Tests for .wikicommit/scripts/record_review.py (Issue #750)"""

import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).parent.parent / ".wikicommit" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from record_review import record_sort_key  # noqa: E402
SCRIPT = SCRIPTS / "record_review.py"

PAGE_REL = ".wikicommit/entity/ja/Person/yamada-taro.md"
RECORD_DIR_REL = ".wikicommit/review/entity/ja/Person/yamada-taro"


def run(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        input=stdin,
        check=False,
    )


def write_page(root: Path, rel: str = PAGE_REL, *, body: str = "本文。", extra: str = "") -> Path:
    """Write a page. `extra` is raw frontmatter lines (each already newline-terminated).

    Built by concatenation rather than an interpolated textwrap.dedent block: an
    unindented interpolation would make the common prefix empty and leave every
    other line indented, producing frontmatter that is not the one under test.
    """
    page = root / rel
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(
        "---\n"
        'title: "山田太郎"\n'
        "lang: ja\n"
        'type: "schema:Person"\n'
        "review_status: pending\n"
        'generated_at: "2026-09-05"\n'
        'generated_by: "claude-opus-5"\n'
        + extra
        + "sources:\n"
        "  - type: url\n"
        "    url: https://example.com/a\n"
        "    hash: sha256:cd34\n"
        "---\n"
        "\n"
        f"{body}\n",
        encoding="utf-8",
    )
    return page


def only_record(root: Path, rel: str = RECORD_DIR_REL) -> dict:
    files = sorted((root / rel).glob("*.md"))
    assert len(files) == 1, files
    text = files[0].read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return yaml.safe_load(text.split("---\n")[1])


def test_records_a_passing_review(tmp_path):
    write_page(tmp_path)
    result = run(
        tmp_path, PAGE_REL,
        "--kind", "ai", "--stage", "generate-pass4",
        "--model", "claude-opus-5[1m]", "--attempts", "1", "--result", "pass",
    )
    assert result.returncode == 0, result.stderr
    assert "RECORDED:" in result.stdout

    fm = only_record(tmp_path)
    assert fm["page"] == PAGE_REL
    assert fm["kind"] == "ai"
    assert fm["stage"] == "generate-pass4"
    assert fm["model"] == "claude-opus-5[1m]"
    assert fm["result"] == "pass"
    assert fm["findings"] == []
    assert fm["page_content_hash"].startswith("sha256:")


def test_source_quote_is_dropped_even_when_passed(tmp_path):
    """The guarantee must not depend on the caller following an instruction."""
    write_page(tmp_path)
    payload = (
        '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","claim":"c",'
        '"source_file":"https://example.com/a","source_lines":"L1-L2",'
        '"source_quote":"VERBATIM SOURCE TEXT","instruction":"fix","round":1}]}'
    )
    result = run(
        tmp_path, PAGE_REL,
        "--kind", "ai", "--stage", "generate-pass4", "--model", "m",
        "--attempts", "2", "--result", "pass", "--json", "-",
        stdin=payload,
    )
    assert result.returncode == 0, result.stderr

    files = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"))
    assert "VERBATIM SOURCE TEXT" not in files[0].read_text(encoding="utf-8")

    finding = only_record(tmp_path)["findings"][0]
    assert "source_quote" not in finding
    # What replaces it has to still be enough to go back and look.
    assert finding["source_file"] == "https://example.com/a"
    assert finding["source_lines"] == "L1-L2"


def test_findings_keep_every_round(tmp_path):
    """Recording only the final round would erase the signal worth keeping."""
    write_page(tmp_path)
    payload = (
        '{"result":"PASS","issues":['
        '{"type":"HALLUCINATION","claim":"a","instruction":"i","round":1},'
        '{"type":"CONTRADICTION","claim":"b","instruction":"i","round":2}]}'
    )
    run(
        tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "m", "--attempts", "3", "--result", "pass", "--json", "-",
        stdin=payload,
    )
    fm = only_record(tmp_path)
    assert [f["round"] for f in fm["findings"]] == [1, 2]
    # attempts is separate because the last round may have found nothing.
    assert fm["attempts"] == 3


def test_empty_source_file_is_preserved(tmp_path):
    """synthesize's MISSING_SOURCE deliberately leaves it empty (Issue #674)."""
    write_page(tmp_path)
    payload = '{"result":"FAIL","issues":[{"type":"MISSING_SOURCE","claim":"c","source_file":"","instruction":"i"}]}'
    run(
        tmp_path, PAGE_REL, "--kind", "ai", "--stage", "synthesize-step5.5",
        "--model", "m", "--result", "fail", "--json", "-", stdin=payload,
    )
    finding = only_record(tmp_path)["findings"][0]
    assert "source_file" in finding and finding["source_file"] == ""


def test_page_content_hash_ignores_the_six_bookkeeping_fields(tmp_path):
    """Shared with reset_review_on_content_change.py, so staleness stays deterministic."""
    write_page(tmp_path)
    run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "m", "--result", "pass")
    first = only_record(tmp_path)["page_content_hash"]

    # Bookkeeping churn: a new generation stamp and an extra source.
    write_page(tmp_path, extra='reviewed_by: "octocat"\ngenerated_with: "0.2.0"\n')
    run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "m", "--result", "pass")
    records = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"), key=record_sort_key)
    second = yaml.safe_load(records[-1].read_text(encoding="utf-8").split("---\n")[1])
    assert second["page_content_hash"] == first

    # A body change is content and must move the hash.
    write_page(tmp_path, body="書き換えた本文。")
    run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "m", "--result", "pass")
    records = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"), key=record_sort_key)
    third = yaml.safe_load(records[-1].read_text(encoding="utf-8").split("---\n")[1])
    assert third["page_content_hash"] != first


def test_reviewed_sources_snapshots_the_page_sources(tmp_path):
    write_page(tmp_path)
    run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "m", "--result", "pass")
    assert only_record(tmp_path)["reviewed_sources"] == [
        {"type": "url", "url": "https://example.com/a", "hash": "sha256:cd34"}
    ]


def test_view_page_records_derived_from(tmp_path):
    view = tmp_path / ".wikicommit/view/ja/agent-loop.md"
    view.parent.mkdir(parents=True, exist_ok=True)
    view.write_text(
        textwrap.dedent("""\
            ---
            title: "エージェントループ"
            lang: ja
            derived_from:
              - path: .wikicommit/entity/ja/Person/yamada-taro.md
                source_commit: abc123
            ---

            body
            """),
        encoding="utf-8",
    )
    result = run(
        tmp_path, ".wikicommit/view/ja/agent-loop.md",
        "--kind", "ai", "--stage", "synthesize-step5.5", "--model", "m", "--result", "pass",
    )
    assert result.returncode == 0, result.stderr
    fm = only_record(tmp_path, ".wikicommit/review/view/ja/agent-loop")
    assert fm["reviewed_sources"][0]["source_commit"] == "abc123"


def test_discarded_page_needs_no_file_and_records_an_empty_hash(tmp_path):
    """The most valuable record: a page the review would not let through."""
    mgmt = tmp_path / ".wikicommit/source/url/example.com/a.md"
    mgmt.parent.mkdir(parents=True, exist_ok=True)
    mgmt.write_text(
        "---\nsource:\n  type: url\n  url: https://example.com/a\n  hash: sha256:cd34\n"
        "status: failed\n---\n",
        encoding="utf-8",
    )
    result = run(
        tmp_path, ".wikicommit/entity/ja/Place/never-written.md",
        "--kind", "ai", "--stage", "generate-pass4", "--model", "m",
        "--attempts", "3", "--result", "discarded",
        "--sources-from", ".wikicommit/source/url/example.com/a.md",
    )
    assert result.returncode == 0, result.stderr
    fm = only_record(tmp_path, ".wikicommit/review/entity/ja/Place/never-written")
    assert fm["page_content_hash"] == ""
    assert fm["reviewed_sources"][0]["url"] == "https://example.com/a"


def test_a_missing_page_is_an_error_unless_discarded(tmp_path):
    result = run(
        tmp_path, ".wikicommit/entity/ja/Place/nope.md",
        "--kind", "ai", "--stage", "generate-pass4", "--model", "m", "--result", "pass",
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_a_page_outside_the_two_trees_is_an_error(tmp_path):
    """A wrong path must not become a silent no-op."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text("---\ntitle: x\n---\n", encoding="utf-8")
    result = run(tmp_path, "docs/x.md", "--kind", "ai", "--stage", "generate-pass4",
                 "--model", "m", "--result", "pass")
    assert result.returncode == 1
    assert ".wikicommit/entity/" in result.stderr


def test_ai_kind_requires_a_model(tmp_path):
    """A verdict that cannot be attributed cannot serve the measurement."""
    write_page(tmp_path)
    result = run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
                 "--result", "pass")
    assert result.returncode == 1
    assert "--model" in result.stderr


def test_human_record_omits_model_and_ai_record_omits_reviewer(tmp_path):
    """Neither key is shipped empty (Issue #553)."""
    write_page(tmp_path)
    run(tmp_path, PAGE_REL, "--kind", "human", "--stage", "issue-close",
        "--reviewer", "octocat", "--result", "pass", "--note", "読んだ。")
    fm = only_record(tmp_path)
    assert fm["reviewer"] == "octocat"
    assert "model" not in fm
    assert "skill_blob" not in fm

    body = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"))[0].read_text(encoding="utf-8")
    assert "読んだ。" in body.split("---\n")[2]


def test_local_human_review_may_omit_the_reviewer(tmp_path):
    """wikicommit-review has no authenticated login to record (Issue #705)."""
    write_page(tmp_path)
    result = run(tmp_path, PAGE_REL, "--kind", "human", "--stage", "review-skill",
                 "--result", "pass")
    assert result.returncode == 0, result.stderr
    assert "reviewer" not in only_record(tmp_path)


def test_records_are_never_overwritten(tmp_path):
    """Immutability is the contract; a same-second collision gets a new name."""
    write_page(tmp_path)
    args = (PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
            "--model", "m", "--result", "pass", "--reviewed-at", "2026-09-05")
    for _ in range(3):
        assert run(tmp_path, *args).returncode == 0
    files = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"))
    assert len(files) == 3
    assert len({f.name for f in files}) == 3


def test_malformed_json_is_an_error(tmp_path):
    write_page(tmp_path)
    result = run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
                 "--model", "m", "--result", "pass", "--json", "-", stdin="{not json")
    assert result.returncode == 1
    assert "JSON" in result.stderr


def test_no_model_id_appears_in_the_filename(tmp_path):
    """A runtime reports e.g. claude-opus-5[1m]; brackets are glob metacharacters."""
    write_page(tmp_path)
    run(tmp_path, PAGE_REL, "--kind", "ai", "--stage", "generate-pass4",
        "--model", "claude-opus-5[1m]", "--result", "pass")
    name = sorted((tmp_path / RECORD_DIR_REL).glob("*.md"))[0].name
    assert "[" not in name and "]" not in name
    assert name.endswith("-ai.md")


def test_collision_suffix_still_orders_chronologically():
    """`-ai-2.md` sorts before `-ai.md` lexically; the reader must not be fooled."""
    names = ["20260905-113550-ai.md", "20260905-113550-ai-2.md", "20260906-090000-ai.md"]
    ordered = [p.name for p in sorted((Path(n) for n in names), key=record_sort_key)]
    assert ordered == [
        "20260905-113550-ai.md",
        "20260905-113550-ai-2.md",
        "20260906-090000-ai.md",
    ]
    # Guard the premise: plain lexical order really does get this wrong.
    assert sorted(names)[0] == "20260905-113550-ai-2.md"


# --- the stamp is clamped so records keep the order they were written in (#991) -------

def test_a_backwards_clock_step_cannot_reorder_two_records(tmp_path):
    """Which review is current is decided by filename order, and that order came
    straight from `datetime.now()` — which is not monotonic. A container whose clock
    is stepped backwards by its host (measured on WSL2: four steps of 0.49-0.58s in
    24 seconds) hands two records written in sequence timestamps in the opposite
    order, and then `standing_review()` reads the *older* one as current.

    Driven at the allocator rather than through the CLI because the failure needs a
    clock that misbehaves; passing the earlier stamp in directly is the same input
    the stepped clock would have produced, without having to reproduce the step.
    """
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    first = allocate_record_path(directory, "20260921-153046", "ai")
    first.write_text("---\n---\n", encoding="utf-8")

    # The clock has gone back across a second boundary since `first` was written.
    second = allocate_record_path(directory, "20260921-153045", "ai")

    assert record_sort_key(second) > record_sort_key(first), (
        f"{second.name} must still sort after {first.name}"
    )


def test_the_clamp_says_that_it_happened(tmp_path, capsys):
    """A clamped record's filename is older than the instant it was written. That is
    the price of keeping the order right, and it is stated rather than absorbed —
    there is no later moment to notice it in, since records are immutable (#750)."""
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    allocate_record_path(directory, "20260921-153046", "ai").write_text("x", encoding="utf-8")
    capsys.readouterr()

    allocate_record_path(directory, "20260921-153045", "ai")

    assert "older than the newest record already here" in capsys.readouterr().err


def test_a_forward_clock_is_left_alone(tmp_path, capsys):
    """The clamp must only engage on an inversion. Firing on the normal case would
    pin every record in a directory to its first stamp."""
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    allocate_record_path(directory, "20260921-153045", "ai").write_text("x", encoding="utf-8")
    capsys.readouterr()

    later = allocate_record_path(directory, "20260921-153046", "ai")

    assert later.name == "20260921-153046-ai.md"
    assert capsys.readouterr().err == ""


def test_a_hand_written_record_does_not_decide_where_the_next_one_sorts(tmp_path):
    """The record tree is meant to be human-writable (#750), so a file whose name
    `record_sort_key()` cannot parse can be sitting in the directory. It sorts on its
    own name and stays visible — but it must not be read as a stamp and clamp every
    machine record after it."""
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    (directory / "notes-from-the-reviewer.md").write_text("x", encoding="utf-8")

    path = allocate_record_path(directory, "20260921-153045", "ai")

    assert path.name == "20260921-153045-ai.md"


def test_a_clamped_record_of_another_kind_still_sorts_after(tmp_path):
    """The clamp has to survive the case the tree is actually shaped like: a page's
    directory holds `ai` records from Pass 4 and `human` records from the tracking
    Issue (§4.8's own example). `kind` is not part of `record_sort_key()`, so
    allocating by "is this filename free" would put the clamped human record at
    `<stamp>-human.md` — *equal* to the ai record rather than after it. `load_records()`
    sorts stably, so equal keys hand `standing_review()` back to `glob()` order, which
    is the arbitrary answer the clamp exists to remove."""
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    machine = allocate_record_path(directory, "20260921-153046", "ai")
    machine.write_text("x", encoding="utf-8")

    human = allocate_record_path(directory, "20260921-153045", "human")

    assert record_sort_key(human) > record_sort_key(machine), (
        f"{human.name} must sort after {machine.name}, not tie with it"
    )


def test_a_stamp_shaped_but_bogus_name_does_not_pin_the_directory(tmp_path):
    """`record_sort_key()` checks that the first two segments are digits but not how
    many, so `99-99-ai.md` parses. `max()` over stamps is a string comparison, so
    such a name would sort above every real stamp and clamp every record written
    afterwards onto it — forever, since records are immutable (#750)."""
    from record_review import allocate_record_path

    directory = tmp_path / "records"
    directory.mkdir()
    (directory / "99-99-ai.md").write_text("x", encoding="utf-8")

    path = allocate_record_path(directory, "20260921-153045", "ai")

    assert path.name == "20260921-153045-ai.md"
