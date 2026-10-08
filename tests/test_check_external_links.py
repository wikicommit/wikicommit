"""check_external_links.py — every page's external links, a few pages per call (Issue #1182)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = (Path(__file__).resolve().parent.parent / ".claude" / "skills" / "wikicommit-init"
           / "scripts" / "templates" / "scripts")

# Records each call (argv and working directory) and prints the JSON in `out`.
FAKE_LYCHEE = '''#!{python}
import json, os, sys
with open("{calls}", "a", encoding="utf-8") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
print(open("{out}").read())
'''


def page(title: str, extra: str = "") -> str:
    return (f"---\ntitle: \"{title}\"\nlang: ja\ntype: \"schema:Person\"\n{extra}"
            "review_status: pending\n---\n\nSee https://example.com/x.\n")


@pytest.fixture
def wiki(tmp_path: Path):
    work = tmp_path / "wiki"
    shutil.copytree(SCRIPTS, work / ".wikicommit" / "scripts",
                    ignore=shutil.ignore_patterns("__pycache__"))
    entity = work / ".wikicommit" / "entity" / "ja" / "Person"
    entity.mkdir(parents=True)
    (entity / "a.md").write_text(page("A"), encoding="utf-8")
    (entity / "b.md").write_text(page("B"), encoding="utf-8")
    (entity / "gone.md").write_text(page("Gone", "status: removed\n"), encoding="utf-8")
    (entity / "index.md").write_text("# Person\n", encoding="utf-8")
    view = work / ".wikicommit" / "view" / "ja"
    view.mkdir(parents=True)
    (view / "v.md").write_text(page("V"), encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    out = tmp_path / "lychee-out"
    out.write_text('{"fail_map": {}}', encoding="utf-8")
    calls = tmp_path / "lychee-calls"
    lychee = bin_dir / "lychee"
    lychee.write_text(FAKE_LYCHEE.format(python=sys.executable, calls=calls, out=out),
                      encoding="utf-8")
    lychee.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    return {"dir": work, "env": env, "out": out, "calls": calls, "bin": bin_dir}


def run(wiki, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, ".wikicommit/scripts/check_external_links.py", *args],
        cwd=wiki["dir"], env=wiki["env"], capture_output=True, text=True, check=False)


def calls(wiki) -> list[dict]:
    if not wiki["calls"].exists():
        return []
    return [json.loads(line) for line in wiki["calls"].read_text(encoding="utf-8").splitlines()]


def test_checks_every_published_page_and_reports_broken_links(wiki):
    a = (wiki["dir"] / ".wikicommit/entity/ja/Person/a.md").resolve()
    wiki["out"].write_text(json.dumps({"fail_map": {str(a): [
        {"url": "https://example.com/x", "status": {"text": "404 Not Found"}}]}}),
        encoding="utf-8")
    result = run(wiki)
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert "BROKEN_LINK: .wikicommit/entity/ja/Person/a.md: https://example.com/x " \
           "(404 Not Found)" in lines
    summary = [line for line in lines if line.startswith("SUMMARY:")]
    assert len(summary) == 1
    assert "pages=3 broken_links=1 not_checked=0" in summary[0]
    assert "checked_at=never" not in summary[0]
    seen = [Path(arg).name for call in calls(wiki) for arg in call["argv"]
            if arg.endswith(".md")]
    assert sorted(seen) == ["a.md", "b.md", "v.md"], (
        "entity and view pages are checked; index.md and removed pages are not")
    for call in calls(wiki):
        assert Path(call["cwd"]) == (wiki["dir"] / ".wikicommit/.cache/lychee").resolve(), (
            "the .lycheecache lands in the ignored cache directory, shared with merge")
        assert "--cache" in call["argv"]
    assert not (wiki["dir"] / ".wikicommit/.cache/lychee/all-pages-progress.json").exists()

    last = run(wiki, "--last")
    assert last.returncode == 0
    assert [line for line in last.stdout.splitlines() if not line.startswith("IN_PROGRESS")] \
        == [line for line in lines if line.startswith(("BROKEN_LINK:", "NOT_CHECKED:", "SUMMARY:"))]
    assert len(calls(wiki)) == 1, "--last never runs lychee"


def test_a_call_returns_early_and_the_next_one_continues(wiki):
    first = run(wiki, "--batch", "1", "--budget", "0")
    assert first.stdout.splitlines() == ["CONTINUE: 1/3 page(s) checked"]
    last = run(wiki, "--last")
    assert "IN_PROGRESS: 1/3 page(s) checked" in last.stdout
    assert "checked_at=never" in last.stdout
    second = run(wiki, "--batch", "1", "--budget", "0")
    assert second.stdout.splitlines() == ["CONTINUE: 2/3 page(s) checked"]
    third = run(wiki, "--batch", "1", "--budget", "0")
    assert "CONTINUE:" not in third.stdout
    assert "pages=3 broken_links=0 not_checked=0" in third.stdout
    seen = [Path(arg).name for call in calls(wiki) for arg in call["argv"]
            if arg.endswith(".md")]
    assert sorted(seen) == ["a.md", "b.md", "v.md"], "no page is checked twice"
    # A completed check is not continued: the next call starts over.
    again = run(wiki, "--batch", "1", "--budget", "0")
    assert again.stdout.splitlines() == ["CONTINUE: 1/3 page(s) checked"]
    restarted = run(wiki, "--restart")
    assert "pages=3" in restarted.stdout


def test_missing_lychee_is_reported_as_not_checked_not_as_clean(wiki):
    (wiki["bin"] / "lychee").unlink()
    env = dict(wiki["env"])
    env["PATH"] = str(wiki["bin"])
    result = subprocess.run(
        [sys.executable, ".wikicommit/scripts/check_external_links.py"],
        cwd=wiki["dir"], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert any(line.startswith("NOT_CHECKED: lychee is not installed")
               for line in result.stdout.splitlines())
    assert "broken_links=0 not_checked=1" in result.stdout


def test_last_with_no_check_ever_run(wiki):
    result = run(wiki, "--last")
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "SUMMARY: checked_at=never pages=0 broken_links=0 not_checked=0"]


# --- Structured findings (Issue #1243) ------------------------------------------

PROGRESS = ".wikicommit/.cache/lychee/all-pages-progress.json"
RESULT = ".wikicommit/.cache/lychee/all-pages-result.json"


def write_json(wiki, rel: str, data) -> None:
    path = wiki["dir"] / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_findings_are_classified_by_kind_not_by_their_wording(wiki):
    a = ".wikicommit/entity/ja/Person/a.md"
    write_json(wiki, RESULT, {"checked_at": "2026-10-07T00:00:00Z", "pages": 3, "findings": [
        {"kind": "not_checked", "pages": [a], "text": "timed out on a.md"},
        {"kind": "broken", "pages": [a], "text": "lychee-looking page: https://x (404)"}]})
    out = run(wiki, "--last").stdout.splitlines()
    assert "NOT_CHECKED: timed out on a.md" in out
    assert "BROKEN_LINK: lychee-looking page: https://x (404)" in out
    assert out[-1].endswith("pages=3 broken_links=1 not_checked=1")


def test_findings_of_pages_gone_since_the_last_call_are_dropped(wiki):
    a, b = ".wikicommit/entity/ja/Person/a.md", ".wikicommit/entity/ja/Person/b.md"
    x, y = ".wikicommit/entity/ja/Person/x.md", ".wikicommit/entity/ja/Person/y.md"
    write_json(wiki, PROGRESS, {"total": 5, "checked": [x, y, a], "findings": [
        {"kind": "broken", "pages": [x], "text": f"{x}: https://x (404)"},
        {"kind": "not_checked", "pages": [x, y], "text": "lychee could not check x, y: boom"},
        {"kind": "not_checked", "pages": [y, a], "text": "lychee could not check y, a: boom"},
        {"kind": "not_checked", "pages": [], "text": "about no page in particular"}]})
    result = run(wiki)
    lines = result.stdout.splitlines()
    assert f"BROKEN_LINK: {x}: https://x (404)" not in lines
    assert "NOT_CHECKED: lychee could not check x, y: boom" not in lines, (
        "a batch-level finding goes once all of its pages are gone")
    assert "NOT_CHECKED: lychee could not check y, a: boom" in lines, (
        "it stays while one of its pages is still checked")
    assert "NOT_CHECKED: about no page in particular" in lines
    seen = [Path(arg).name for call in calls(wiki) for arg in call["argv"]
            if arg.endswith(".md")]
    assert sorted(seen) == ["b.md", "v.md"], f"{b} and the view page were left to check"
    stored = json.loads((wiki["dir"] / RESULT).read_text(encoding="utf-8"))["findings"]
    assert all(set(f) == {"kind", "pages", "text"} for f in stored)


def test_a_progress_file_of_plain_strings_is_discarded(wiki):
    a = ".wikicommit/entity/ja/Person/a.md"
    write_json(wiki, PROGRESS, {"total": 3, "checked": [a],
                                "findings": [f"{a}: https://old (404)"]})
    result = run(wiki)
    assert "BROKEN_LINK" not in result.stdout
    assert "pages=3 broken_links=0 not_checked=0" in result.stdout
    seen = [Path(arg).name for call in calls(wiki) for arg in call["argv"]
            if arg.endswith(".md")]
    assert sorted(seen) == ["a.md", "b.md", "v.md"], "the check started over"


def test_a_result_file_of_plain_strings_is_still_read(wiki):
    write_json(wiki, RESULT, {"checked_at": "2026-10-06T00:00:00Z", "pages": 3, "findings": [
        ".wikicommit/entity/ja/Person/a.md: https://x (404)",
        "lychee is not installed; the external links of the pages were not checked"]})
    out = run(wiki, "--last").stdout.splitlines()
    assert out == [
        "BROKEN_LINK: .wikicommit/entity/ja/Person/a.md: https://x (404)",
        "NOT_CHECKED: lychee is not installed; the external links of the pages were not checked",
        "SUMMARY: checked_at=2026-10-06T00:00:00Z pages=3 broken_links=1 not_checked=1"]
