"""The Skills work when installed under `.agents/skills/` alone (Issue #1021).

`npx skills add --agent codex` creates no `.claude/skills/`. Before Issue #1021 that
broke three things at once, none of them loudly:

- every Pass of `/wikicommit-generate` sat behind a pointer written as
  `.claude/skills/wikicommit-generate/references/…`, so the run could not enter Pass 1;
- `record_run.py --token` looked only under `.claude/skills/` and stamped a pass that
  was read exactly as instructed as `token: missing`;
- `check_distribution_freshness.py` reported "wikicommit-init is not installed" and an
  all-zero summary, so the version-skew check at the start of a run went blank.

A real Codex run is Issue #732's to make. Until then these tests reproduce the one
thing that differs — where the Skill tree is — in a temporary directory that has
`.agents/skills/` and nothing else, installed the way `install.sh --agents` installs it.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).parent.parent
SKILLS = REPO / ".claude" / "skills"
SCRIPTS = SKILLS / "wikicommit-init" / "scripts" / "templates" / "scripts"
_PRUNE = shutil.ignore_patterns("node_modules", "__pycache__")

sys.path.insert(0, str(REPO / "tools"))
from check_distributed_path_refs import DISTRIBUTED_SKILLS  # noqa: E402

# A path an instruction resolves against its own Skill directory. The lookbehind keeps
# `.wikicommit/scripts/x.py` (a repository-root path) from being read as `scripts/x.py`.
_SKILL_RELATIVE_RE = re.compile(
    r"(?<![\w./-])((?:\.\./wikicommit-[\w-]+/|references/|scripts/)[\w./-]*\.(?:md|py|json|yaml))"
)


@pytest.fixture(scope="module")
def agents_only(tmp_path_factory) -> Path:
    """A repository with the Skills under `.agents/skills/` and no `.claude/` at all."""
    repo = tmp_path_factory.mktemp("codex-only")
    result = subprocess.run(
        ["bash", str(REPO / "install.sh"), "--agents", "--yes"],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not (repo / ".claude").exists()
    return repo


def test_install_sh_agents_puts_every_skill_under_agents_skills(agents_only):
    installed = sorted(p.name for p in (agents_only / ".agents" / "skills").iterdir())
    assert installed == sorted(DISTRIBUTED_SKILLS)


def test_every_skill_relative_path_resolves_in_an_agents_only_install(agents_only):
    """The instructions find their own files — the Pass 1 pointer included.

    Every `references/…`, `scripts/…` and `../wikicommit-…/…` path an instruction names
    is resolved against the Skill directory it sits in, inside a tree that has only
    `.agents/skills/`. A path that does not resolve is a step the agent cannot take.
    """
    root = agents_only / ".agents" / "skills"
    missing = []
    for skill in DISTRIBUTED_SKILLS:
        skill_dir = root / skill
        for md in skill_dir.rglob("*.md"):
            rel = md.relative_to(skill_dir).parts
            if md.name == "CHANGELOG.md" or "changelog" in rel or rel[:1] == ("scripts",):
                continue
            for match in _SKILL_RELATIVE_RE.finditer(md.read_text(encoding="utf-8")):
                target = match.group(1)
                if not (skill_dir / target).exists():
                    missing.append(f"{md.relative_to(root)}: {target}")
    assert not missing, "unresolvable Skill-relative paths:\n" + "\n".join(missing)


def test_generate_points_at_its_pass_files_relative_to_itself(agents_only):
    """The specific break Issue #1021 was filed for: the Pass 1 pointer."""
    skill_md = (agents_only / ".agents/skills/wikicommit-generate/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "Read `references/pass1-extract.md` now and follow it" in skill_md
    assert (agents_only / ".agents/skills/wikicommit-generate/references/pass1-extract.md").is_file()


def test_no_distributed_instruction_names_a_fixed_skill_tree_path():
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_skill_tree_paths.py")],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "errors=0" in result.stdout


def test_the_guard_catches_a_reintroduced_fixed_path(tmp_path):
    md = tmp_path / ".claude/skills/wikicommit-merge/SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "Run `python .claude/skills/wikicommit-init/scripts/init.py`.\n"
        "Installed under `.claude/skills/` (or `.agents/skills/`).\n"
        "Or `.claude/skills/wikicommit-init/x.py` under `.agents/skills/` for Codex.\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_skill_tree_paths.py")],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "SKILL.md:1:" in result.stdout
    assert "errors=1" in result.stdout


# --- record_run.py --token --------------------------------------------------------


def _record_run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "record_run.py"), *args],
        cwd=cwd, capture_output=True, text=True, check=False,
    )


def _open_run(cwd: Path) -> str:
    out = _record_run(cwd, "start", "--skill", "wikicommit-generate").stdout
    line = next(ln for ln in out.splitlines() if ln.startswith("RUN_STARTED:"))
    return line.split(" ", 2)[1]


def _last_token(cwd: Path, run: str) -> str:
    front = yaml.safe_load((cwd / run).read_text(encoding="utf-8").split("---\n")[1])
    return front["passes"][-1]["token"]


def _pass_file(root: Path, token: str) -> None:
    path = root / "wikicommit-generate" / "references" / "pass1-extract.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\npass_token: {token}\n---\n\n# Pass 1\n", encoding="utf-8")


def test_token_is_found_under_agents_skills(tmp_path):
    _pass_file(tmp_path / ".agents" / "skills", "p1-abc")
    run = _open_run(tmp_path)
    result = _record_run(tmp_path, "checkpoint", run, "--pass", "pass1-extract",
                         "--token", "p1-abc")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _last_token(tmp_path, run) == "ok"


def test_token_backed_by_either_copy_is_ok(tmp_path):
    """With `--copy` for two agents, a drifted copy must not call a read pass skipped."""
    _pass_file(tmp_path / ".claude" / "skills", "old")
    _pass_file(tmp_path / ".agents" / "skills", "new")
    run = _open_run(tmp_path)
    for token in ("old", "new"):
        result = _record_run(tmp_path, "checkpoint", run, "--pass", "pass1-extract",
                             "--token", token)
        assert result.returncode == 0, result.stdout
        assert _last_token(tmp_path, run) == "ok"
    result = _record_run(tmp_path, "checkpoint", run, "--pass", "pass1-extract",
                         "--token", "neither")
    assert result.returncode == 1
    assert _last_token(tmp_path, run) == "mismatch"


def test_token_with_no_skill_tree_is_still_missing(tmp_path):
    run = _open_run(tmp_path)
    result = _record_run(tmp_path, "checkpoint", run, "--pass", "pass1-extract",
                         "--token", "p1-abc")
    assert result.returncode == 1
    assert _last_token(tmp_path, run) == "missing"
    assert ".claude/skills/wikicommit-generate/references/pass1-extract.md" in result.stdout + result.stderr


# --- check_distribution_freshness.py -------------------------------------------------


def test_freshness_finds_templates_under_agents_skills(tmp_path):
    init_dir = tmp_path / ".agents" / "skills" / "wikicommit-init"
    shutil.copytree(SKILLS / "wikicommit-init", init_dir, ignore=_PRUNE)
    init = subprocess.run(
        [sys.executable, str(init_dir / "scripts" / "init.py"), "--primary-lang", "en"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert init.returncode == 0, init.stdout + init.stderr
    result = subprocess.run(
        [sys.executable, str(tmp_path / ".wikicommit/scripts/check_distribution_freshness.py"),
         "--repo-root", str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert "not installed" not in result.stdout, result.stdout
    assert "VERSION:" in result.stdout
    assert "installed=unknown" not in result.stdout


# --- tools/check_skill_tool_names.py (Issue #1015) ---------------------------------


def test_no_distributed_instruction_names_a_claude_code_tool():
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_skill_tool_names.py")],
        cwd=REPO, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout
    assert "errors=0" in result.stdout


def test_the_tool_name_guard_catches_wrapped_and_plain_forms(tmp_path):
    md = tmp_path / ".claude/skills/wikicommit-fix/SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "Read the file with the Read tool.\n"
        "Fetch it with WebFetch.\n"
        "Run these as direct Bash\ntool invocations.\n"
        "Read the page in full and write the result.\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_skill_tool_names.py")],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "SKILL.md:1:" in result.stdout
    assert "SKILL.md:2:" in result.stdout
    assert "SKILL.md:3:" in result.stdout
    assert "errors=3" in result.stdout
