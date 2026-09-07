"""Tests for tools/check_distributed_path_refs.py (Issue #549)"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "tools" / "check_distributed_path_refs.py"
TEMPLATES_REL = Path(".claude/skills/wikicommit-init/scripts/templates")


def run(cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_skills_dir(tmp_path):
    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_clean_skill_md_passes(tmp_path):
    write(tmp_path, ".claude/skills/wikicommit-merge/SKILL.md",
          "Squash-merge the PR once the quality gates pass (Issue #456).\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_designdoc_reference_in_skill_md_is_an_error(tmp_path):
    write(tmp_path, ".claude/skills/wikicommit-merge/SKILL.md",
          "See `docs/DesignDoc-pipeline.md` §6.2 for the rationale.\n")

    result = run(tmp_path)
    assert result.returncode == 1
    assert "ERROR: .claude/skills/wikicommit-merge/SKILL.md:1" in result.stdout
    assert "docs/DesignDoc-pipeline.md" in result.stdout
    assert "errors=1" in result.stdout


def test_issues_and_dev_references_are_errors(tmp_path):
    write(tmp_path, ".claude/skills/wikicommit-generate/SKILL.md",
          "Origin: Issues/registered/p3-205-foo.md\n"
          "Seen in dev/pilot-ai-driven-dev-wiki-round3.md\n")

    result = run(tmp_path)
    assert result.returncode == 1
    assert "Issues/registered/p3-205-foo.md" in result.stdout
    assert "dev/pilot-ai-driven-dev-wiki-round3.md" in result.stdout
    assert "errors=2" in result.stdout


def test_template_payload_is_in_scope(tmp_path):
    write(tmp_path, str(TEMPLATES_REL / "scripts" / "check_orphans.py"),
          '"""Detect orphans (docs/DesignDoc-ScriptSpec.md)."""\n')

    result = run(tmp_path)
    assert result.returncode == 1
    assert "check_orphans.py:1" in result.stdout


def test_quartz_plugins_source_is_an_error(tmp_path):
    """quartz-plugins/ used to be DEFERRED (reported, exit 0). Its references
    are gone and the plugins have been rebuilt (Issue #644), so it is held to
    the same rule as every other distributed file."""
    write(tmp_path, str(TEMPLATES_REL / "quartz-plugins" / "wikicommit-sources" / "src" / "a.tsx"),
          "// see docs/DesignDoc-data.md §4.3\n")

    result = run(tmp_path)
    assert result.returncode == 1
    assert "ERROR:" in result.stdout
    assert "DEFERRED:" not in result.stdout
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_quartz_plugins_committed_dist_is_an_error(tmp_path):
    """A comment removed from src/ but left in the committed dist/ bundle still
    ships — the rebuild is part of clearing the reference, not optional."""
    write(tmp_path, str(TEMPLATES_REL / "quartz-plugins" / "wikicommit-properties" / "dist" / "index.js"),
          "// adds (docs/DesignDoc-data.md §4.1, Issue #495)\n")

    result = run(tmp_path)
    assert result.returncode == 1
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_quartz_plugins_committed_sourcemap_is_an_error(tmp_path):
    """The bundler strips most comments from dist/*.js, so a stale reference
    left behind by a missing rebuild often survives only in the committed
    .js.map's sourcesContent — which ships too, and must be scanned."""
    write(tmp_path,
          str(TEMPLATES_REL / "quartz-plugins" / "wikicommit-explorer" / "dist" / "index.js.map"),
          '{"sources":["../src/util/foldLang.ts"],'
          '"sourcesContent":["// see docs/DesignDoc-data.md \u00a73.3\\n"]}\n')

    result = run(tmp_path)
    assert result.returncode == 1
    assert "SUMMARY: checked=1, errors=1" in result.stdout


def test_example_docs_path_is_not_flagged(tmp_path):
    # wikicommit-collect's candidate list shows illustrative user paths such as
    # `docs/notes/meeting-0512.md`; only docs/DesignDoc-* names this repository.
    write(tmp_path, ".claude/skills/wikicommit-collect/SKILL.md",
          "2. docs/notes/meeting-0512.md — (brief reason for relevance)\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_node_modules_is_skipped(tmp_path):
    write(tmp_path, str(TEMPLATES_REL / "quartz-plugins" / "p" / "node_modules" / "x.js"),
          "// docs/DesignDoc-data.md\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_non_distributed_skill_is_out_of_scope(tmp_path):
    write(tmp_path, ".claude/skills/implement-issue/SKILL.md",
          "Follow docs/DesignDoc-skills.md §11.7.\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=0, errors=0" in result.stdout


def test_repository_itself_is_clean():
    result = run(REPO_ROOT)
    assert result.returncode == 0, result.stdout


def test_bare_designdoc_filename_is_an_error(tmp_path):
    # Dropping the `docs/` prefix names the same undistributed file, so it must
    # not be a way around the guard.
    write(tmp_path, ".claude/skills/wikicommit-remove/SKILL.md",
          "Soft-deletes the page (`DesignDoc-data.md` \u00a74.5).\n")

    result = run(tmp_path)
    assert result.returncode == 1
    assert "DesignDoc-data.md" in result.stdout
    assert "errors=1" in result.stdout


def test_dev_tld_url_is_not_flagged(tmp_path):
    # A `.dev` top-level domain is not this repository's dev/ directory.
    write(tmp_path, ".claude/skills/wikicommit-serve/SKILL.md",
          "See https://vite.dev/config/ for the upstream options.\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: checked=1, errors=0" in result.stdout


def test_distributed_skills_matches_install_sh():
    """DISTRIBUTED_SKILLS is a hand-copy of install.sh's SKILLS array; a Skill
    added to one but not the other would ship unguarded."""
    sys.path.insert(0, str(SCRIPT.parent))
    try:
        import check_distributed_path_refs as mod
    finally:
        sys.path.pop(0)

    line = next(
        ln for ln in (REPO_ROOT / "install.sh").read_text(encoding="utf-8").splitlines()
        if ln.startswith("SKILLS=(")
    )
    install_sh_skills = re.findall(r'"([^"]+)"', line)

    assert install_sh_skills == mod.DISTRIBUTED_SKILLS
