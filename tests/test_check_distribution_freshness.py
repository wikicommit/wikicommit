"""Tests for .wikicommit/scripts/check_distribution_freshness.py (Issue #712).

Three pilots were all running the same stale `review-issue-close-sync.yml`, the same
stale `quartz-plugins/` dist and the same stale `*.cjs`, and the only way anyone found
out was cloning each one and diffing against the template by hand. init.py now refreshes
that payload; this script is how a repository says whether it needs to.

The load-bearing property is not "it finds drift" but "it stays quiet when there is
none". Every `review` file that can never byte-match a real repository — the two with
placeholders, the two whose body is a replace-me comment, and `.gitignore`, which init
appends a Quartz section to — has to report nothing on a freshly initialized repository.
A warning that is always on stops being read, which is the failure Issue #562 already
had to undo once for the low-density guard, and it would take this report down with it.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
INIT_SCRIPTS = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts"
SCRIPT_REL = Path(".wikicommit") / "scripts" / "check_distribution_freshness.py"

# The fourth place that copies this tree, and the last one to prune it. install.sh
# (`find ... -not -path '*/node_modules/*'`), copy_tree() in init.py (Issue #211, and
# __pycache__ since Issue #577) and check_distribution_freshness.py itself (_PRUNED_DIRS)
# all skip these two, so neither can reach a user's wiki repository. A fixture that
# carries them anyway is not just slow — once `npm install` has been run under a template
# directory (a fresh checkout has no node_modules at all, which is why the cost is
# invisible in CI and brutal locally), 38,242 of the 38,567 files under templates/ are
# node_modules, copied once per test — it also puts the checker in front of a tree the
# product cannot produce. Anything added here has to keep pruning them.
_PRUNE = shutil.ignore_patterns("node_modules", "__pycache__")


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / SCRIPT_REL), "--repo-root", str(repo), *args],
        capture_output=True,
        text=True,
    )


def _load_script_module():
    """The checker imported in-process, for the unit-level assertions below."""
    import importlib.util

    path = INIT_SCRIPTS / "templates" / "scripts" / "check_distribution_freshness.py"
    spec = importlib.util.spec_from_file_location("_check_distribution_freshness", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(out: str) -> dict[str, int]:
    line = next(ln for ln in out.splitlines() if ln.startswith("SUMMARY:"))
    return {
        k.strip(): int(v)
        for k, v in (part.split("=") for part in line.removeprefix("SUMMARY:").split(","))
    }


@pytest.fixture(scope="module")
def initialized(tmp_path_factory) -> Path:
    """A repository initialized exactly as `/wikicommit-init --quartz --quartz-pages`
    leaves it, with the Skill tree installed so the templates are reachable."""
    repo = tmp_path_factory.mktemp("wiki")
    shutil.copytree(
        INIT_SCRIPTS,
        repo / ".claude" / "skills" / "wikicommit-init" / "scripts",
        ignore=_PRUNE,
    )
    result = subprocess.run(
        [sys.executable, str(repo / ".claude/skills/wikicommit-init/scripts/init.py"),
         "--quartz", "--quartz-pages", "--primary-lang", "ja"],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return repo


@pytest.fixture
def repo(initialized, tmp_path) -> Path:
    """A per-test copy, so a test that introduces drift cannot leak into the next."""
    work = tmp_path / "repo"
    shutil.copytree(initialized, work, symlinks=True, ignore=_PRUNE)
    return work


def test_a_freshly_initialized_repository_reports_nothing(repo):
    result = _run(repo)
    assert result.returncode == 0
    assert _summary(result.stdout) == {"outdated": 0, "missing": 0, "orphan": 0}


@pytest.mark.parametrize(
    "path",
    [".wikicommit/config.yml", "quartz.config.yaml",
     ".wikicommit/source-policy.md", ".wikicommit/entity-policy.md", ".gitignore"],
)
def test_files_that_can_never_byte_match_are_not_reported_when_untouched(repo, path):
    """These five are why `review` reports additive signals rather than byte diffs:
    two substitute placeholders at init time, two ship a body that says to replace it,
    and .gitignore gets a Quartz section appended. Byte comparison would light all five
    permanently on every repository that exists."""
    assert path not in _run(repo).stdout


def test_a_user_editing_a_review_file_is_not_drift(repo):
    """Setting a theme and a target language is the user doing their job."""
    config = repo / ".wikicommit" / "config.yml"
    config.write_text(
        config.read_text(encoding="utf-8")
        .replace('theme: ""', 'theme: "私の Wiki"')
        .replace("targets: []", "targets: [en]"),
        encoding="utf-8",
    )
    assert ".wikicommit/config.yml" not in _run(repo).stdout


def test_a_key_added_upstream_is_reported_on_that_file_alone(repo):
    """The Issue #570 case: `index_only:` shipped with a consumer that reads it, and
    repositories initialized earlier had no such key and no way to learn that."""
    template = repo / ".claude/skills/wikicommit-init/scripts/templates/source-policy.md"
    template.write_text(
        template.read_text(encoding="utf-8").replace("wikicommit:\n", "wikicommit:\n  brand_new_key: []\n", 1),
        encoding="utf-8",
    )
    out = _run(repo).stdout
    assert "OUTDATED: .wikicommit/source-policy.md" in out
    assert "brand_new_key" in out
    assert _summary(out)["outdated"] == 1


def test_a_nested_key_added_upstream_is_reported(repo):
    """quartz.config.yaml has three top-level keys and never gains a fourth — the keys
    that actually arrive are nested (pageTitleSuffix, under `configuration`, in Issue
    #679). A top-level-only comparison would report nothing here, forever."""
    template = repo / ".claude/skills/wikicommit-init/scripts/templates/quartz.config.yaml"
    template.write_text(
        template.read_text(encoding="utf-8").replace(
            "  pageTitle: {PAGE_TITLE}\n", "  pageTitle: {PAGE_TITLE}\n  brandNewKey: true\n", 1
        ),
        encoding="utf-8",
    )
    out = _run(repo).stdout
    assert "OUTDATED: quartz.config.yaml" in out
    assert "configuration.brandNewKey" in out


def test_a_key_added_upstream_to_config_yml_is_reported(repo):
    """config.yml's placeholders are not all bare: `wikicommit_version` ships its
    placeholder already inside double quotes, so a neutralizer that substitutes an empty
    quoted string leaves four quote characters in a row and the whole template stops
    parsing. The key set then comes back empty, `template - local` is empty too, and this
    file can never report anything — silently, with a clean SUMMARY. The
    quartz.config.yaml test above passes either way, which is why it went unnoticed."""
    template = repo / ".claude/skills/wikicommit-init/scripts/templates/config.yml"
    template.write_text(
        template.read_text(encoding="utf-8") + "\nbrand_new_key: 1\n", encoding="utf-8"
    )
    out = _run(repo).stdout
    assert "OUTDATED: .wikicommit/config.yml" in out
    assert "brand_new_key" in out


@pytest.mark.parametrize("template_rel", ["config.yml", "quartz.config.yaml"])
def test_a_placeholder_template_still_parses_after_neutralization(template_rel):
    """The direct form of the same guard: an unparseable template yields an empty key
    set, which is indistinguishable from "nothing was added upstream"."""
    module = _load_script_module()
    keys = module._yaml_keys(INIT_SCRIPTS / "templates" / template_rel, is_template=True)
    assert keys, f"templates/{template_rel} produced no keys — did it fail to parse?"


def test_config_yml_template_exposes_the_keys_worth_comparing():
    module = _load_script_module()
    keys = module._yaml_keys(INIT_SCRIPTS / "templates" / "config.yml", is_template=True)
    assert {"wikicommit_version", "theme", "translation.targets"} <= keys


def test_a_skill_present_but_unloadable_says_so_rather_than_saying_uninstalled(repo):
    """"Install the Skills" would send the reader after the wrong thing when the Skill is
    installed and it is the list that will not load."""
    module = repo / ".claude/skills/wikicommit-init/scripts/_root_outputs.py"
    module.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0
    assert "could not be loaded" in result.stdout
    assert "is not installed" not in result.stdout
    assert _summary(result.stdout) == {"outdated": 0, "missing": 0, "orphan": 0}


def test_stale_wikicommit_payload_is_reported(repo):
    """The drift measured in all three pilots."""
    (repo / ".github/workflows/review-issue-close-sync.yml").write_text("# stale\n", encoding="utf-8")
    (repo / "install-local-plugins.cjs").write_text("// stale\n", encoding="utf-8")
    (repo / "quartz-plugins/wikicommit-banner/dist/index.js").write_text("// stale\n", encoding="utf-8")
    out = _run(repo).stdout
    assert "OUTDATED: .github/workflows/review-issue-close-sync.yml (overwrite)" in out
    assert "OUTDATED: install-local-plugins.cjs (overwrite)" in out
    assert "OUTDATED: quartz-plugins (overwrite)" in out


def test_a_deleted_file_is_reported_missing(repo):
    (repo / ".wikicommit" / "entity-policy.md").unlink()
    out = _run(repo).stdout
    assert "MISSING: .wikicommit/entity-policy.md" in out
    assert _summary(out)["missing"] == 1


def test_a_renamed_upstream_script_leaves_a_reported_orphan(repo):
    """copy_tree never deletes (Issue #583), so refreshing a tree is not mirroring it."""
    (repo / ".wikicommit" / "scripts" / "check_old_name.py").write_text("pass\n", encoding="utf-8")
    out = _run(repo).stdout
    assert "ORPHAN: .wikicommit/scripts/check_old_name.py" in out
    assert _summary(out)["orphan"] == 1


def test_a_user_authored_schema_type_is_not_an_orphan(repo):
    """`.wikicommit/schema/` is `review`, not `overwrite`: a file the template lacks is
    a custom type the user wrote or Pass 2b added, not a leftover. Reporting it would
    make the orphan line mean two opposite things."""
    custom = repo / ".wikicommit" / "schema" / "custom"
    custom.mkdir(parents=True, exist_ok=True)
    (custom / "Decision.md").write_text("---\ntype: schema:custom/Decision\n---\n", encoding="utf-8")
    out = _run(repo).stdout
    assert "Decision" not in out
    assert _summary(out)["orphan"] == 0


def test_quartz_plugin_dev_artifacts_are_not_reported_missing(repo):
    """init deliberately does not copy vitest/eslint config or *.test.ts. Without the
    shared exclusion every one of them would be MISSING on every single run."""
    out = _run(repo).stdout
    assert "vitest.config.ts" not in out
    assert ".test.ts" not in out


def test_version_line_reports_both_sides(repo):
    assert "VERSION: synced=" in _run(repo).stdout
    assert "installed=" in _run(repo).stdout


def test_a_repository_without_wikicommit_version_still_runs(repo):
    """Repositories initialized before Issue #577 have no stamp. The version is reported
    for the reader and never gates a comparison, so every other path is judged exactly as
    it would be otherwise.

    config.yml itself is the one exception, and correctly so: the key the template gained
    upstream is `wikicommit_version`, so the additive comparison names it — which is the
    whole point of that comparison, and the actionable half of `synced=unknown`."""
    config = repo / ".wikicommit" / "config.yml"
    data = [ln for ln in config.read_text(encoding="utf-8").splitlines()
            if not ln.startswith("wikicommit_version")]
    config.write_text("\n".join(data) + "\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0
    assert "synced=unknown" in result.stdout
    assert "OUTDATED: .wikicommit/config.yml" in result.stdout
    assert "wikicommit_version" in result.stdout
    assert _summary(result.stdout) == {"outdated": 1, "missing": 0, "orphan": 0}


def test_without_the_skill_installed_it_warns_and_reports_nothing(repo):
    """.wikicommit/scripts/ is committed to the wiki repository; .claude/skills/ is
    installed separately and may be absent. Degrade the way the vocabulary checks do."""
    shutil.rmtree(repo / ".claude")
    result = _run(repo)
    assert result.returncode == 0
    assert "WARNING:" in result.stdout
    assert _summary(result.stdout) == {"outdated": 0, "missing": 0, "orphan": 0}


def test_an_unknown_update_policy_is_treated_as_review(repo):
    """An old .wikicommit/scripts/ against a newer _root_outputs.py. Must not crash, and
    must not read an unrecognized policy as permission to ignore the file."""
    module = repo / ".claude/skills/wikicommit-init/scripts/_root_outputs.py"
    module.write_text(
        module.read_text(encoding="utf-8").replace(
            'UPDATE_POLICIES = ("overwrite", "review", "skip")',
            'UPDATE_POLICIES = ("overwrite", "review", "skip", "policy-from-the-future")',
        ).replace(
            'RootOutput(".lychee.toml", ALL, origin="init", template=".lychee.toml")',
            'RootOutput(".lychee.toml", ALL, origin="init", template=".lychee.toml", '
            'update="policy-from-the-future")',
        ),
        encoding="utf-8",
    )
    (repo / ".lychee.toml").write_text("# drifted\n", encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0
    assert "OUTDATED: .lychee.toml (review)" in result.stdout


def test_the_variant_is_detected_and_can_be_overridden(repo):
    """quartz.config.yaml and deploy.yml are what the two flags actually add, so they
    are what the detection reads."""
    assert _summary(_run(repo).stdout)["missing"] == 0
    (repo / ".github" / "workflows" / "deploy.yml").unlink()
    assert _summary(_run(repo).stdout)["missing"] == 0, "quartz_only must not want deploy.yml"
    out = _run(repo, "--variant", "quartz_pages").stdout
    assert "MISSING: .github/workflows/deploy.yml" in out


def test_exit_code_is_always_zero_even_with_findings(repo):
    (repo / "install-local-plugins.cjs").write_text("// stale\n", encoding="utf-8")
    (repo / ".wikicommit" / "entity-policy.md").unlink()
    result = _run(repo)
    assert result.returncode == 0
    assert _summary(result.stdout)["outdated"] >= 1
    assert _summary(result.stdout)["missing"] >= 1


def test_it_never_writes_to_the_repository(repo):
    """Unlike check_ingest_freshness.py, this one has no side effects."""
    before = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}
    _run(repo)
    after = {p: p.stat().st_mtime_ns for p in repo.rglob("*") if p.is_file()}
    assert before == after


def test_config_yaml_placeholders_are_not_read_as_structure(repo):
    """`theme: {THEME}` is a value slot, but YAML reads an unquoted `{...}` as a flow
    mapping — so the template appears to have a nested key named THEME that no real
    config.yml has. This was caught by running the check against a clean init."""
    config = yaml.safe_load((repo / ".wikicommit" / "config.yml").read_text(encoding="utf-8"))
    assert isinstance(config["theme"], str)
    assert ".wikicommit/config.yml" not in _run(repo).stdout
