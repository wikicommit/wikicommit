"""The public subset's `pytest` is checked before someone remembers to (Issue #795).

`wikicommit/wikicommit` is a strict subset built by copying a whitelist out of
this repository, so **one test that reads a `REPO_ROOT` path outside that set
breaks the public subset silently**. Issue #788 measured the drift: 3 failures
(2026-08-31) → 4 → 14 → 16, and the increase came not from new tests but from
existing ones starting to read a non-published root file — nobody writing a test
against `.gitignore` thinks of it as a publication-boundary change.

That Issue fixed the 16 and centralized the discriminator in
`tests/_publication.py`. It did not stop the next one. `check_publication_subset.sh`
does, and this file is what keeps that guard wired up: a check nothing invokes
checks nothing, and the failure mode here is exactly the silent one the guard
exists to end.

Everything here reads paths outside the published set (`dev/`, `.github/`), so
every test skips in the published snapshot — which is the same rule it enforces.
"""

from _publication import REPO_ROOT, skip_unless_development_repository

SCRIPT = REPO_ROOT / "dev" / "scripts" / "check_publication_subset.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"


def test_the_guard_script_exists_and_is_executable():
    skip_unless_development_repository("dev/scripts/ is not published")
    assert SCRIPT.is_file(), SCRIPT
    # The workflow and the sync procedure both invoke it through `bash`, so the
    # bit is not load-bearing there — it is for the human who runs it directly.
    assert SCRIPT.stat().st_mode & 0o111, "not executable"


def test_ci_runs_the_guard():
    """A guard nothing invokes is the silent failure it exists to prevent."""
    skip_unless_development_repository(".github/workflows/ is not published")
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "dev/scripts/check_publication_subset.sh" in text


def test_the_guard_stays_inside_the_consolidated_job():
    """Issue #591 merged five jobs into one because Actions bills per job, rounded
    up to the minute. A separate job for this would rebuild that waste, so the
    invocation belongs among the other `run_check` calls in `checks` — not under a
    `jobs:` key of its own."""
    skip_unless_development_repository(".github/workflows/ is not published")
    import yaml

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert set(workflow["jobs"]) == {"checks", "quartz-plugins"}, (
        "a third job means the guard (or something else) was split back out"
    )
    steps = workflow["jobs"]["checks"]["steps"]
    body = "\n".join(str(step.get("run", "")) for step in steps)
    assert "dev/scripts/check_publication_subset.sh" in body
    assert 'run_check "check_publication_subset"' in body


def test_the_guard_stages_from_the_snapshot_script_rather_than_its_own_list():
    """`dev/publication-scope.md` §6: the machine-readable copy of what is
    published lives in `snapshot_push.sh` and nowhere else. A second list here
    would be the drift Issue #788 was about, one layer down."""
    skip_unless_development_repository("dev/scripts/ is not published")
    text = SCRIPT.read_text(encoding="utf-8")
    assert "snapshot_push.sh" in text
    assert "PUBLISHED_PATHS" not in text, "the published list must not be restated here"


def test_the_guard_says_that_it_reads_head_not_the_working_tree():
    """`git archive` stages the commit, so a fix that is only on disk is not
    checked. Passing silently there would be a false green in exactly the
    situation someone is trying to verify a fix."""
    skip_unless_development_repository("dev/scripts/ is not published")
    text = SCRIPT.read_text(encoding="utf-8")
    assert "git status --porcelain" in text
    assert "WARNING:" in text
