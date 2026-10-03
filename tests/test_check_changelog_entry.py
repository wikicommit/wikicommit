"""tools/check_changelog_entry.py (Issue #1029)."""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import check_changelog_entry as guard  # noqa: E402

SKILL = ".claude/skills/wikicommit-generate/SKILL.md"


def test_payload_paths():
    assert guard.is_payload(SKILL)
    assert guard.is_payload(".claude/skills/wikicommit-init/scripts/templates/scripts/x.py")
    assert guard.is_payload(".claude/skills/wikicommit-relate/agents/openai.yaml")
    # Not payload: other skills, the CHANGELOG copies, dist/, tests.
    assert not guard.is_payload(".claude/skills/implement-issue/SKILL.md")
    assert not guard.is_payload(".claude/skills/wikicommit-init/CHANGELOG.md")
    assert not guard.is_payload(".claude/skills/wikicommit-init/changelog/0.7.0.md")
    plugin = ".claude/skills/wikicommit-init/scripts/templates/quartz-plugins/wikicommit-banner"
    assert not guard.is_payload(f"{plugin}/dist/index.js")
    assert not guard.is_payload(f"{plugin}/src/i18n/index.test.ts")
    assert not guard.is_payload(f"{plugin}/test/__mocks__/x.ts")
    assert not guard.is_payload("tests/test_x.py")
    assert not guard.is_payload("docs/DesignDoc-skills.md")


def test_payload_without_entry_fails():
    code, lines = guard.judge([SKILL], [])
    assert code == 1
    assert "was not touched" in lines[-1]


def test_entry_or_exemption_passes():
    assert guard.judge([SKILL, "CHANGELOG.md"], [])[0] == 0
    assert guard.judge([SKILL], ["none — comment-only change"])[0] == 0
    assert guard.judge([SKILL], ["none: refactor with identical output"])[0] == 0


def test_exemption_without_reason_fails_even_when_not_needed():
    for value in ("none", "none —", "skip"):
        code, lines = guard.judge(["tests/test_x.py"], [value])
        assert code == 1, value
        assert lines[0].startswith("ERROR:")


def test_no_payload_passes():
    assert guard.judge(["tests/test_x.py", "docs/a.md"], [])[0] == 0


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_end_to_end_reads_branch_diff_and_trailers(tmp_path):
    repo = tmp_path
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    skill = repo / SKILL
    skill.parent.mkdir(parents=True)
    skill.write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    _git(repo, "checkout", "-q", "-b", "feature")
    skill.write_text("b\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "change")

    def run():
        return subprocess.run(
            [sys.executable, str(REPO / "tools/check_changelog_entry.py"), "--base", "main"],
            cwd=repo, capture_output=True, text=True,
        )

    result = run()
    assert result.returncode == 1, result.stdout

    skill.write_text("c\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "comment only\n\nChangelog: none — comment-only change")
    result = run()
    assert result.returncode == 0, result.stdout
    assert "comment-only change" in result.stdout
