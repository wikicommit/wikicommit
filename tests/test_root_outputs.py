"""Tests for .claude/skills/wikicommit-init/scripts/_root_outputs.py (Issue #642).

The list of root-level outputs was previously maintained three times: once as
init.py's copy calls, once as print_next_steps.py's `git add` strings, and once
as prose in wikicommit-init/SKILL.md. Issue #556 showed what that costs — a file
added to the first list only (install-local-plugins.cjs) broke the first GitHub
Pages build of every --quartz-pages repository. The first two are now one list;
these tests hold the invariants that list relies on, and check the third (the
prose, which cannot be generated) against it.

tests/test_smoke_local.py owns the end-to-end direction — running init.py for
real and asserting the printed `git add` leaves nothing untracked.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts"
TEMPLATES_DIR = SCRIPTS_DIR / "templates"
SKILL_MD = SCRIPTS_DIR.parent / "SKILL.md"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
_spec = importlib.util.spec_from_file_location("_root_outputs", SCRIPTS_DIR / "_root_outputs.py")
_root_outputs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_root_outputs)


def test_every_entry_belongs_to_at_least_one_known_variant():
    for entry in _root_outputs.ROOT_OUTPUTS:
        assert entry.variants, f"{entry.path} はどの variant にも属していません"
        unknown = entry.variants - set(_root_outputs.VARIANTS)
        assert not unknown, f"{entry.path} が未知の variant を指しています: {unknown}"


def test_paths_are_unique():
    paths = [entry.path for entry in _root_outputs.ROOT_OUTPUTS]
    assert len(paths) == len(set(paths))


def test_origins_and_conditions_are_known_values():
    """`origin` and `condition` decide whether an entry reaches init.py's copies and
    the printed `git add`, and an unrecognized value fails open on both sides (not
    "init" means never copied; not "always" means listed only alongside the vocabulary
    cache). A typo would therefore read as a deliberate exclusion — the silent drift
    this list replaces — so the module rejects one at import time."""
    for entry in _root_outputs.ROOT_OUTPUTS:
        assert entry.origin in _root_outputs.ORIGINS, f"{entry.path}: 未知の origin {entry.origin!r}"
        assert entry.condition in _root_outputs.CONDITIONS, (
            f"{entry.path}: 未知の condition {entry.condition!r}"
        )


def test_unknown_condition_is_rejected_rather_than_treated_as_conditional():
    """A CONDITIONS member added without a branch in `_condition_holds()` must fail
    loudly instead of quietly keying off `vocab_cache_created`."""
    with pytest.raises(ValueError):
        _root_outputs._condition_holds("npm_installed", vocab_cache_created=True)


def test_only_init_generated_entries_carry_a_template():
    """A template path means "init.py copies this verbatim", so it is only
    meaningful for what init.py itself writes — a submodule the user adds or an
    npm side effect has no template to copy from."""
    for entry in _root_outputs.ROOT_OUTPUTS:
        if entry.template is not None:
            assert entry.origin == "init", f"{entry.path}: origin={entry.origin} に template があります"


def test_declared_templates_exist():
    for entry in _root_outputs.ROOT_OUTPUTS:
        if entry.template is None:
            continue
        assert (TEMPLATES_DIR / entry.template).is_file(), (
            f"{entry.path} のテンプレート templates/{entry.template} が存在しません"
        )


@pytest.mark.parametrize("variant", _root_outputs.VARIANTS)
def test_git_add_paths_omit_entries_guided_separately(variant):
    """package-lock.json is deliberately kept out of the `git add` line — it is a
    side effect of `npm install`, and `git add` aborts on a pathspec that does not
    exist, which would take the whole foundational commit down with it (Issue #556).
    print_next_steps.py guides it as its own command instead."""
    guided_separately = {e.path for e in _root_outputs.ROOT_OUTPUTS if not e.in_git_add}
    assert guided_separately, "in_git_add=False のエントリが 1 つも無く、この検証が空振りしています"
    assert not guided_separately & set(_root_outputs.git_add_paths(variant, vocab_cache_created=True))


@pytest.mark.parametrize("variant", _root_outputs.VARIANTS)
def test_conditional_paths_appear_only_when_the_condition_holds(variant):
    conditional = {e.path for e in _root_outputs.ROOT_OUTPUTS if e.condition != "always"}
    assert conditional, "condition 付きのエントリが 1 つも無く、この検証が空振りしています"
    assert not conditional & set(_root_outputs.git_add_paths(variant, vocab_cache_created=False))
    assert conditional <= set(_root_outputs.git_add_paths(variant, vocab_cache_created=True))


def test_quartz_pages_is_a_superset_of_quartz_only():
    """--quartz-pages is --quartz plus deploy.yml; nothing is dropped by opting
    into publishing."""
    quartz_only = _root_outputs.git_add_paths("quartz_only")
    quartz_pages = _root_outputs.git_add_paths("quartz_pages")
    assert set(quartz_only) < set(quartz_pages)
    assert set(quartz_pages) - set(quartz_only) == {".github/workflows/deploy.yml"}


# SKILL.md の「--quartz で何が生成されるか」を列挙している段落の開始・終了アンカー。
# ファイル全体を対象に部分文字列検索すると、この列挙から漏れても他の箇所（`package.json` は
# npm install の手順説明に、`deploy.yml` は --quartz-pages の確認プロンプトに、
# `quartz.config.yaml` は --repo-url の説明に、`repair-plugin-builds.cjs` は末尾の補足に、
# それぞれ独立して登場する）が一致してしまい、Issue #556 と同種のドリフトを取り逃がす。
_SKILL_MD_GENERATED_BLOCK_START = "When `--quartz` is given, in addition to"
_SKILL_MD_GENERATED_BLOCK_END = "These root-level files are never overwritten"


def _skill_md_generated_outputs_block() -> str:
    """SKILL.md のうち、生成されるルートレベル成果物を列挙している段落だけを返す。"""
    skill_md = SKILL_MD.read_text(encoding="utf-8")
    start = skill_md.find(_SKILL_MD_GENERATED_BLOCK_START)
    assert start != -1, (
        f"SKILL.md に列挙段落の開始アンカー {_SKILL_MD_GENERATED_BLOCK_START!r} が見つかりません"
        "（段落を書き換えたならこのアンカーも更新してください。見つからないまま通すと"
        "この検証が空振りします）"
    )
    end = skill_md.find(_SKILL_MD_GENERATED_BLOCK_END, start)
    assert end != -1, (
        f"SKILL.md に列挙段落の終了アンカー {_SKILL_MD_GENERATED_BLOCK_END!r} が見つかりません"
    )
    return skill_md[start:end]


def test_skill_md_prose_mentions_every_quartz_gated_output():
    """SKILL.md's own description of what `--quartz` generates is the third copy
    of this list, and it is prose — it cannot be generated from the table, only
    checked against it.

    Scoped to the Quartz-gated outputs, which is what that paragraph enumerates
    (and the class Issue #556's drift fell into). The always-generated entries
    are described in other terms across the file — `.gitignore`,
    `.wikicommit/entity/` and review-issue-close-sync.yml do not appear by path
    at all — so requiring them here would assert something the document was never
    written to satisfy.

    The search is scoped to that paragraph rather than the whole file: over half
    of these paths are also mentioned elsewhere in SKILL.md for unrelated reasons,
    so a whole-file substring check would still pass with the path deleted from
    the enumeration — the exact drift this is meant to catch.
    """
    block = _skill_md_generated_outputs_block()
    all_variants = set(_root_outputs.VARIANTS)
    for entry in _root_outputs.ROOT_OUTPUTS:
        if entry.origin != "init" or set(entry.variants) == all_variants:
            continue
        assert entry.path in block, (
            f"{entry.path} が wikicommit-init/SKILL.md の生成物の説明に出てきません"
            "（_root_outputs.py に追加したら SKILL.md の散文も更新してください）"
        )


# ── update policies (Issue #712) ─────────────────────────────────────────────
#
# Until Issue #712, init.py restated ownership as a literal flag at each call site, and
# two paths (.wikicommit/config.yml, .wikicommit/schema/) carried no flag at all — so
# --no-overwrite was the only thing standing between a re-init and the user's theme,
# targets and hand-edited type templates. These pin the classification itself, with the
# reason each path got the policy it did, so a later edit has to argue with the reason
# rather than silently flip a string.

EXPECTED_UPDATE_POLICIES = {
    # WikiCommit's own payload: the user never authors it, so a re-init refreshes it.
    ".wikicommit/scripts": ("overwrite", "shared quality-gate scripts the Skills call (Issue #647)"),
    "quartz-plugins": ("overwrite", "dist/ is committed pre-built; nothing here is user-editable"),
    ".github/workflows/deploy.yml": ("overwrite", "WikiCommit's own workflow; user CI goes in other files"),
    ".github/workflows/review-issue-close-sync.yml": ("overwrite", "same — and it was stale in all three pilots"),
    "prebuild-symlinks.cjs": ("overwrite", "pure build script"),
    "repair-plugin-builds.cjs": ("overwrite", "pure build script"),
    "install-local-plugins.cjs": ("overwrite", "pure build script — the Issue #556 file"),
    ".wikicommit/review-rules.md": ("overwrite", "WikiCommit's review discipline, not the user's"),
    # The user holds values, prose or local adjustments here; init must never clobber it.
    ".wikicommit/config.yml": ("review", "holds theme/targets the user set"),
    "quartz.config.yaml": ("review", "pageTitle and footer links are per-repository"),
    "package.json": ("review", "may be merged with the repository's own"),
    ".wikicommit/schema": ("review", "the one tree humans may edit directly"),
    ".lychee.toml": ("review", "tunable per repository"),
    ".markdownlint.json": ("review", "tunable per repository"),
    ".github/ISSUE_TEMPLATE/report.md": ("review", "localizable"),
    ".gitignore": ("review", "the repository's own ignores live here too"),
    # Prose is the user's, but the frontmatter keys grow upstream (Issue #570's
    # index_only:), so these are reported rather than skipped.
    ".wikicommit/source-policy.md": ("review", "frontmatter keys are added upstream"),
    ".wikicommit/entity-policy.md": ("review", "frontmatter keys are added upstream"),
    # Not ours to compare.
    ".claude": ("skip", "installed by install.sh, not init"),
    ".wikicommit/entity": ("skip", "the user's pages"),
    ".wikicommit/view": ("skip", "the user's pages"),
    ".wikicommit/source": ("skip", "the user's source management files"),
    ".wikicommit/review": ("skip", "the wiki's own accumulated review history"),
    ".gitmodules": ("skip", "the user's own git submodule add"),
    "quartz": ("skip", "the user's own git submodule add"),
    ".wikicommit/schemaorg-vocab.json": ("skip", "regenerable cache"),
    "package-lock.json": ("skip", "npm side effect"),
}


def test_every_entry_has_the_expected_update_policy():
    actual = {entry.path: entry.update for entry in _root_outputs.ROOT_OUTPUTS}
    expected = {path: policy for path, (policy, _why) in EXPECTED_UPDATE_POLICIES.items()}
    assert actual == expected


def test_update_policies_are_known_values():
    for entry in _root_outputs.ROOT_OUTPUTS:
        assert entry.update in _root_outputs.UPDATE_POLICIES, entry.path
        assert entry.compare in _root_outputs.COMPARISONS, entry.path


def test_skip_and_none_comparison_are_declared_together():
    """Two statements of one decision; letting them disagree leaves an entry either
    silently never checked or checked against nothing."""
    for entry in _root_outputs.ROOT_OUTPUTS:
        assert (entry.update == "skip") == (entry.compare == "none"), entry.path


def test_the_default_update_policy_is_the_protective_one():
    """An entry added without an explicit decision must not overwrite the user's file —
    the same rule init.py already applies when both copy flags are passed."""
    entry = _root_outputs.RootOutput("x", _root_outputs.ALL, origin="init")
    assert entry.update == "review"


@pytest.mark.parametrize("bad", [{"update": "overwrite", "compare": "none"},
                                 {"update": "skip", "compare": "bytes"},
                                 {"update": "nonsense"},
                                 {"compare": "nonsense"}])
def test_validate_rejects_inconsistent_or_unknown_policies(bad):
    kwargs = {"update": "review", "compare": "bytes", **bad}
    entry = _root_outputs.RootOutput("x", _root_outputs.ALL, origin="init", **kwargs)
    original = _root_outputs.ROOT_OUTPUTS
    try:
        _root_outputs.ROOT_OUTPUTS = original + (entry,)
        with pytest.raises(ValueError):
            _root_outputs._validate()
    finally:
        _root_outputs.ROOT_OUTPUTS = original


def test_unknown_update_policy_falls_back_to_review_rather_than_raising():
    """`npx skills add` refreshes .claude/skills/ while .wikicommit/scripts/ only catches
    up on the next init, so an old checker can read a policy a newer list introduced.
    Falling back to the conservative end keeps that from crashing — or, worse, from
    reading an unrecognized policy as permission to overwrite."""
    entry = _root_outputs.RootOutput("x", _root_outputs.ALL, origin="init", update="policy-from-the-future")
    assert _root_outputs.update_policy(entry) == "review"
    assert _root_outputs.copy_flags(entry) == {"always_skip_existing": True}


def test_copy_flags_map_policies_to_init_flags():
    overwrite = _root_outputs.by_path(".wikicommit/scripts")
    review = _root_outputs.by_path(".wikicommit/config.yml")
    assert _root_outputs.copy_flags(overwrite) == {"always_overwrite": True}
    assert _root_outputs.copy_flags(review) == {"always_skip_existing": True}


def test_compare_templates_exist_and_never_duplicate_template():
    for entry in _root_outputs.ROOT_OUTPUTS:
        if entry.compare_template is None:
            continue
        assert entry.template is None, f"{entry.path}: template と compare_template の両方を持っています"
        assert (TEMPLATES_DIR / entry.compare_template).exists(), (
            f"{entry.path} の compare_template templates/{entry.compare_template} が存在しません"
        )


def test_every_comparable_entry_has_something_to_compare_against():
    """A `review`/`overwrite` entry with no template resolves to "never reported",
    which is `skip` under a name that claims otherwise."""
    for entry in _root_outputs.ROOT_OUTPUTS:
        if entry.update == "skip" or entry.origin != "init":
            continue
        assert _root_outputs.template_source(entry) is not None, entry.path


def test_quartz_plugin_dev_artifacts_are_recognized_here():
    """init.py excludes these from the copy and the freshness check must make the same
    exclusion, or it reports every one of them as MISSING on every run (Issue #712)."""
    is_dev = _root_outputs.is_quartz_plugin_dev_artifact
    assert is_dev(Path("wikicommit-banner/vitest.config.ts"))
    assert is_dev(Path("wikicommit-banner/eslint.config.js"))
    assert is_dev(Path("wikicommit-banner/src/build.test.ts"))
    assert is_dev(Path("wikicommit-banner/src/components/WikiCommitBanner.test.tsx"))
    assert not is_dev(Path("wikicommit-banner/dist/index.js"))
    assert not is_dev(Path("wikicommit-banner/src/index.ts"))
