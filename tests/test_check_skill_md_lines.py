"""Tests for tools/check_skill_md_lines.py"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "tools" / "check_skill_md_lines.py"


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_skill_md(root: Path, skill_name: str, line_count: int) -> Path:
    skill_dir = root / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("\n".join(f"line {i}" for i in range(line_count)) + "\n", encoding="utf-8")
    return skill_md


def test_no_skills_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, over_limit=0" in result.stdout


def test_skill_md_under_limit_no_warning(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 100)

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" not in result.stdout
    assert "SUMMARY: checked=1, over_limit=0" in result.stdout


def test_skill_md_at_limit_no_warning(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 500)

    result = run(["--limit=500"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" not in result.stdout
    assert "SUMMARY: checked=1, over_limit=0" in result.stdout


def test_skill_md_over_limit_warns(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 501)

    result = run(["--limit=500"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING: .claude/skills/wikicommit-merge/SKILL.md: 501 lines (limit: 500)" in result.stdout
    assert "SUMMARY: checked=1, over_limit=1" in result.stdout


def test_custom_limit_applies(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 20)

    result = run(["--limit=10"], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING: .claude/skills/wikicommit-merge/SKILL.md: 20 lines (limit: 10)" in result.stdout
    assert "SUMMARY: checked=1, over_limit=1" in result.stdout


def test_multiple_skills_only_over_limit_ones_warn(tmp_path):
    write_skill_md(tmp_path, "wikicommit-generate", 600)
    write_skill_md(tmp_path, "wikicommit-init", 50)

    result = run(["--limit=500"], cwd=tmp_path)
    assert result.returncode == 0
    assert "wikicommit-generate/SKILL.md: 600 lines" in result.stdout
    assert "wikicommit-init/SKILL.md" not in result.stdout
    assert "SUMMARY: checked=2, over_limit=1" in result.stdout


def test_default_limit_is_500(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 501)

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert "limit: 500" in result.stdout
