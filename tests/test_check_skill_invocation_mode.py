"""Tests for tools/check_skill_invocation_mode.py (#234)"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "tools" / "check_skill_invocation_mode.py"


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_skill_md(root: Path, skill_name: str, frontmatter_lines: list[str]) -> Path:
    skill_dir = root / ".claude" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    body = "---\n" + "\n".join(frontmatter_lines) + "\n---\n\n# body\n"
    skill_md.write_text(body, encoding="utf-8")
    return skill_md


def test_no_skills_dir(tmp_path):
    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, unset=0" in result.stdout


def test_skill_with_flag_set_not_listed(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", ["name: wikicommit-merge", "disable-model-invocation: true"])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "INFO" not in result.stdout
    assert "SUMMARY: checked=1, unset=0" in result.stdout


def test_skill_without_flag_is_listed(tmp_path):
    write_skill_md(tmp_path, "wikicommit-ask", ["name: wikicommit-ask", "description: Answer questions"])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "INFO: .claude/skills/wikicommit-ask/SKILL.md: disable-model-invocation not set" in result.stdout
    assert "SUMMARY: checked=1, unset=1" in result.stdout


def test_flag_set_to_false_is_treated_as_unset(tmp_path):
    write_skill_md(tmp_path, "wikicommit-ask", ["name: wikicommit-ask", "disable-model-invocation: false"])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "INFO: .claude/skills/wikicommit-ask/SKILL.md: disable-model-invocation not set" in result.stdout
    assert "SUMMARY: checked=1, unset=1" in result.stdout


def test_mixed_skills_only_unset_ones_listed(tmp_path):
    write_skill_md(tmp_path, "wikicommit-generate", ["name: wikicommit-generate", "disable-model-invocation: true"])
    write_skill_md(tmp_path, "wikicommit-search", ["name: wikicommit-search", "description: Search"])

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "wikicommit-generate/SKILL.md" not in result.stdout
    assert "wikicommit-search/SKILL.md: disable-model-invocation not set" in result.stdout
    assert "SUMMARY: checked=2, unset=1" in result.stdout


def test_non_mapping_frontmatter_is_listed_without_crashing(tmp_path):
    skill_dir = tmp_path / ".claude" / "skills" / "list-frontmatter"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n- foo\n- bar\n---\n\n# body\n", encoding="utf-8")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "INFO: .claude/skills/list-frontmatter/SKILL.md: disable-model-invocation not set" in result.stdout
    assert "SUMMARY: checked=1, unset=1" in result.stdout


def test_skill_md_without_frontmatter_is_listed(tmp_path):
    skill_dir = tmp_path / ".claude" / "skills" / "no-frontmatter"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# no frontmatter here\n", encoding="utf-8")

    result = run(cwd=tmp_path)
    assert result.returncode == 0
    assert "INFO: .claude/skills/no-frontmatter/SKILL.md: disable-model-invocation not set" in result.stdout
    assert "SUMMARY: checked=1, unset=1" in result.stdout
