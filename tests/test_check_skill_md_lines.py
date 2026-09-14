"""Tests for tools/check_skill_md_lines.py

Two metrics since Issue #887 — the instruction surface (every instruction `.md`
the Skill can reach, in bytes) and the `SKILL.md` body (lines and bytes) — so
these tests assert on both, and specifically on the case that motivated the
second one: moving prose into a sibling file must move the body figure without
moving the surface figure.
"""

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


def write_md(root: Path, skill_name: str, rel: str, line_count: int) -> Path:
    path = root / ".claude" / "skills" / skill_name / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"line {i}" for i in range(line_count)) + "\n", encoding="utf-8")
    return path


def write_skill_md(root: Path, skill_name: str, line_count: int) -> Path:
    return write_md(root, skill_name, "SKILL.md", line_count)


def test_no_skills_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, over_surface=0, over_body_lines=0" in result.stdout


def test_a_small_skill_is_quiet(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 100)

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "WARNING" not in result.stdout
    assert "SUMMARY: checked=1, over_surface=0, over_body_lines=0" in result.stdout


def test_a_directory_without_a_skill_md_is_not_counted(tmp_path):
    """A `scripts/`-only directory, or a stray folder, is not a Skill."""
    (tmp_path / ".claude" / "skills" / "not-a-skill").mkdir(parents=True)
    write_skill_md(tmp_path, "wikicommit-merge", 10)

    result = run([], cwd=tmp_path)
    assert "SUMMARY: checked=1," in result.stdout


# ── The instruction surface (bytes) ──────────────────────────────────────────

def test_surface_at_the_limit_is_quiet(tmp_path):
    path = write_skill_md(tmp_path, "wikicommit-merge", 1)
    size = len(path.read_bytes())

    result = run([f"--limit={size}"], cwd=tmp_path)
    assert "WARNING" not in result.stdout
    assert "over_surface=0" in result.stdout


def test_surface_over_the_limit_warns(tmp_path):
    path = write_skill_md(tmp_path, "wikicommit-merge", 1)
    size = len(path.read_bytes())

    result = run([f"--limit={size - 1}"], cwd=tmp_path)
    assert f"WARNING: .claude/skills/wikicommit-merge: surface {size} B (over {size - 1})" in result.stdout
    assert "over_surface=1" in result.stdout


def test_the_surface_sums_every_instruction_md_in_the_directory(tmp_path):
    """The point of the metric: a sibling file counts.

    This is the regression the old line-only metric could not catch — the same
    prose in two files measured as less than the same prose in one.
    """
    body = write_skill_md(tmp_path, "wikicommit-generate", 20)
    extra = write_md(tmp_path, "wikicommit-generate", "regenerate.md", 20)
    total = len(body.read_bytes()) + len(extra.read_bytes())

    result = run([f"--limit={total - 1}"], cwd=tmp_path)
    assert f"surface {total} B" in result.stdout
    assert "2 instruction files: SKILL.md + regenerate.md" in result.stdout


def test_splitting_a_skill_moves_the_body_figure_but_not_the_surface(tmp_path):
    """`body ↓` with `surface →` is what a split looks like, and both numbers are
    needed to see it: the body figure alone reports a split as an improvement."""
    write_skill_md(tmp_path, "wikicommit-generate", 600)
    before = run(["--limit=1"], cwd=tmp_path).stdout
    before_surface = int(before.split("surface ")[1].split(" B")[0])
    assert "SKILL.md 600 lines" in before

    # Move the last 200 lines into a sibling file, keeping the same prose.
    path = tmp_path / ".claude" / "skills" / "wikicommit-generate" / "SKILL.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:400]) + "\n", encoding="utf-8")
    (path.parent / "regenerate.md").write_text("\n".join(lines[400:]) + "\n", encoding="utf-8")

    after = run(["--limit=1"], cwd=tmp_path).stdout
    after_surface = int(after.split("surface ")[1].split(" B")[0])
    # The body figure is still printed even though 400 lines is under the line
    # limit — that is what makes the pair readable, and it is the reading that
    # says "this was split" rather than "this got smaller".
    assert "SKILL.md 400 lines (ok" in after
    assert after_surface == before_surface, "the surface must not shrink just because a file was split"


def test_the_changelog_payload_is_not_instructions(tmp_path):
    """`wikicommit-init` carries a CHANGELOG so that it reaches an installed wiki.
    It is never read as instructions, so it must not inflate the surface."""
    body = write_skill_md(tmp_path, "wikicommit-init", 10)
    write_md(tmp_path, "wikicommit-init", "CHANGELOG.md", 5000)
    write_md(tmp_path, "wikicommit-init", "changelog/0.4.0.md", 5000)
    size = len(body.read_bytes())

    result = run([f"--limit={size}"], cwd=tmp_path)
    assert "WARNING" not in result.stdout


def test_expanded_templates_are_not_charged_to_the_skill(tmp_path):
    """`scripts/templates/` is expanded into a wiki repository. Some of those files
    are read by Skills, but at their installed paths and by several Skills at once,
    so they cannot be charged to any one of them."""
    body = write_skill_md(tmp_path, "wikicommit-init", 10)
    write_md(tmp_path, "wikicommit-init", "scripts/templates/review-rules.md", 5000)
    size = len(body.read_bytes())

    result = run([f"--limit={size}"], cwd=tmp_path)
    assert "WARNING" not in result.stdout


def test_the_default_surface_limit_is_40000(tmp_path):
    path = write_md(tmp_path, "wikicommit-merge", "SKILL.md", 5000)  # ~9 bytes/line
    assert len(path.read_bytes()) > 40_000

    result = run([], cwd=tmp_path)
    assert "over 40000" in result.stdout
    assert "over_surface=1" in result.stdout


# ── The SKILL.md body (lines) ────────────────────────────────────────────────

def test_body_at_the_line_limit_is_quiet(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 500)

    result = run(["--body-line-limit=500", "--limit=999999"], cwd=tmp_path)
    assert "WARNING" not in result.stdout
    assert "over_body_lines=0" in result.stdout


def test_body_over_the_line_limit_warns_with_bytes_alongside(tmp_path):
    path = write_skill_md(tmp_path, "wikicommit-merge", 501)
    size = len(path.read_bytes())

    result = run(["--body-line-limit=500", "--limit=999999"], cwd=tmp_path)
    assert f"SKILL.md 501 lines (over 500), {size} B" in result.stdout
    assert "over_body_lines=1" in result.stdout


def test_the_default_body_line_limit_is_500(tmp_path):
    write_skill_md(tmp_path, "wikicommit-merge", 501)

    result = run(["--limit=999999"], cwd=tmp_path)
    assert "(over 500)" in result.stdout
    assert "over_body_lines=1" in result.stdout


def test_only_the_skills_over_a_threshold_are_named(tmp_path):
    write_skill_md(tmp_path, "wikicommit-generate", 600)
    write_skill_md(tmp_path, "wikicommit-remove", 50)

    result = run(["--body-line-limit=500", "--limit=999999"], cwd=tmp_path)
    assert "wikicommit-generate: surface" in result.stdout
    assert "SKILL.md 600 lines (over 500)" in result.stdout
    assert "wikicommit-remove" not in result.stdout
    assert "SUMMARY: checked=2, over_surface=0, over_body_lines=1" in result.stdout


def test_this_repository_still_exits_zero(tmp_path):
    """Non-blocking by design: it reports, it never fails a build."""
    result = run([], cwd=Path(__file__).parent.parent)
    assert result.returncode == 0
    assert "SUMMARY: checked=" in result.stdout
