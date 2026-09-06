#!/usr/bin/env python3
"""Render wikicommit-init step 3's "next steps" guidance text (Issue #350).

Before this script existed, SKILL.md hardcoded three near-identical copies of this
guidance (one per --quartz / --quartz-pages combination), differing only in a handful
of lines (the git add file list, the commit message, a couple of sentences). That
duplication pushed SKILL.md past its recommended line limit even though the choice
of which lines to print is fully deterministic given the flags the agent already
computed in steps 2-3 (deterministic, repetitive text belongs in a script, not
duplicated prose). The agent computes the flags (variant chosen in
Prerequisites, install-check results, GitHub Pages activation outcome) and passes them
here; this script owns the branching and renders the final text to print verbatim to
the user.

Usage:
    python .claude/skills/wikicommit-init/scripts/print_next_steps.py \\
      --variant {none,quartz_only,quartz_pages} \\
      [--lychee-installed] [--markitdown-installed] \\
      [--actions-pr-permission-enabled] \\
      [--package-json-skipped] \\
      [--quartz-status STATUS] [--install-plugins-status {ok,failed}] \\
      [--pages-html-url URL] [--vocab-cache-created]

Exit code: always 0. Argument errors (e.g. missing --variant) exit 2 via argparse.
"""

import argparse
import sys

import _root_outputs

QUARTZ_STATUSES = [
    "fully_set_up",
    "npm_install_completed_fully_set_up",
    "npm_install_completed_submodule_pending",
    "npm_install_failed_submodule_exists",
    "npm_install_failed_no_submodule",
]

_INSTALL_PLUGINS_NOTE = (
    "\n\n   Note: `npm run install-plugins` fetches WikiCommit's community Quartz plugins from their\n"
    "   upstream repositories and commonly takes several minutes the first time; it is a fast no-op\n"
    "   on later runs (already-installed plugins are skipped). Running it here means that cost is\n"
    "   paid once, now, instead of silently landing on whichever `/wikicommit-serve` run happens\n"
    "   to call it first."
)

_QUARTZ_SETUP_FULL = (
    "Set up Quartz v5 (the core is pulled in as a git submodule, not an npm package):\n"
    "   git submodule add https://github.com/jackyzha0/quartz.git quartz\n"
    "   npm install\n"
    "   npm run install-plugins" + _INSTALL_PLUGINS_NOTE
)
_QUARTZ_SETUP_NPM_ONLY = (
    "Set up Quartz v5 (the core is pulled in as a git submodule, not an npm package):\n"
    "   npm install\n"
    "   npm run install-plugins" + _INSTALL_PLUGINS_NOTE
)
_QUARTZ_SETUP_NPM_INSTALL_ONLY = (
    "Set up Quartz v5 (the core is pulled in as a git submodule, not an npm package):\n"
    "   npm install"
)

_INSTALL_PLUGINS_STEP = (
    "Install Quartz community plugins (the automatic attempt during wikicommit-init did not\n"
    "   succeed):\n"
    "   npm run install-plugins" + _INSTALL_PLUGINS_NOTE
)

_PREVIEW_STEP = (
    "Preview the wiki locally anytime{deploy_suffix}:\n"
    "   /wikicommit-serve          # builds the wiki and serves it locally (npm run preview)\n"
    "   /wikicommit-serve --build  # builds only, without starting a local server (npm run build)\n"
    "\n"
    "   Windows only: `npm run install-plugins` (part of both commands above) shells out to\n"
    "   Quartz's own `npx quartz plugin install`, which symlinks quartz-plugins/* into\n"
    "   quartz/.quartz/plugins/. Quartz's symlink logic is third-party code this project does\n"
    "   not control, and plain NTFS symlinks require either enabling Developer Mode\n"
    "   (Settings > Privacy & Security > For developers) or running as Administrator; without\n"
    "   one of those, the wikicommit-* plugins (JSON-LD, Explorer, banner, language switcher,\n"
    "   breadcrumbs, sources) silently fail to load into the preview. This is unrelated to\n"
    "   prebuild-symlinks.cjs (Issue #273), which only handles quartz/content and\n"
    "   quartz/quartz.config.yaml and needs no such privilege (directory junction + file-copy\n"
    "   fallback). Either way (symlink or the file-copy fallback), `git status` inside the\n"
    "   quartz/ submodule may show these as untracked/modified — this is expected and\n"
    "   harmless: `git add quartz` from the repo root only records the submodule's commit\n"
    "   pointer, never these generated build artifacts, so there is nothing to clean up."
)

_LYCHEE_STEP = (
    "Install lychee (used for external link validation):\n"
    "   cargo install lychee\n"
    "   or: https://github.com/lycheeverse/lychee#installation"
)

_MARKITDOWN_STEP = (
    "Install markitdown (used by /wikicommit-generate to extract type: url / type: wikicommit sources,\n"
    "   and as the type: path .pdf fallback when the pdf skill is unavailable):\n"
    "   pip install 'markitdown[pdf]'"
)

_REGISTER_STEP = "Register a source with /wikicommit-generate <file path or URL>."

_COMMIT_STEP_INTRO = (
    'Commit the generated foundational files (`/wikicommit-merge` only targets\n'
    '   "changes" under `.wikicommit/entity/` and `.wikicommit/source/`, so\n'
    "   `.claude/skills/`, `.wikicommit/config.yml`, `.wikicommit/schema/`,\n"
    "   `.wikicommit/scripts/`, `.wikicommit/entity/`, `.wikicommit/source/`,\n"
    "   {extra_files}will never get committed anywhere\n"
    "   in the pipeline unless committed here. This command is meant for the user to run\n"
    "   themselves — the agent must not run it on the user's behalf (writes to main are prohibited):\n"
    "   {git_add}\n"
    '   git commit -m "{commit_msg}"\n'
    "   git push"
)

_QUARTZ_PAGES_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (Issue #313 — needed for the tracking-Issue\n"
    "   review flow, regardless of the Quartz choice), `.github/ISSUE_TEMPLATE/report.md`\n"
    '   (Issue #339 — backs the wikicommit-banner report link, which otherwise silently\n'
    "   no-ops), and the root-level publishing configuration files "
)
_QUARTZ_ONLY_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (Issue #313 — needed for the tracking-Issue\n"
    "   review flow, regardless of the Quartz choice), `.github/ISSUE_TEMPLATE/report.md`\n"
    '   (Issue #339 — backs the wikicommit-banner report link, which otherwise silently\n'
    "   no-ops), and the root-level local-build configuration files "
)
_NONE_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (Issue #313 — needed for the tracking-Issue\n"
    "   review flow), and the quality gate configuration files "
)

# package-lock.json は上の `git add` 行に含めず、別コマンドとして案内する（Issue #556 の
# 対応方針3の結論）。init.py の生成物ではなく Quartz セットアップ手順の `npm install` の
# 副産物であり、npm install が失敗した場合・ユーザーがその手順を飛ばした場合には存在しない。
# `git add` は存在しない pathspec を渡されるとコマンド全体が異常終了するため（_root_outputs.py が
# .wikicommit/schemaorg-vocab.json を condition="vocab_cache" にしているのと同じ理由）、同じ行に
# 足すと基盤ファイルのコミットそのものが丸ごと失敗しうる。deploy.yml は `npm ci`
# ではなく `npm install` を使うため lock file は必須ではなく（Issue #556 が扱う CI 失敗の
# 原因でもない）、CI とローカルで解決される依存バージョンを揃えるための任意の推奨に留める。
# 案内文からは手順番号（「step 1 の npm install」等）を参照しない: build_quartz_setup_step が
# None / _INSTALL_PLUGINS_STEP を返す分岐では npm install 手順そのものが番号付きリストから
# 消え、番号がずれる。--quartz 単体（deploy.yml なし）でも成り立つ書き方にしておく。
_PACKAGE_LOCK_NOTE = (
    "\n\n"
    "   Also commit the root `package-lock.json` once `npm install` has created one — it pins the\n"
    "   dependency versions a fresh clone resolves, including the GitHub Pages build workflow if\n"
    "   this repository has (or later enables) one. It is deliberately kept out of the command\n"
    "   above because `git add` aborts on a pathspec that does not exist, which would take the\n"
    "   whole foundational commit down with it if `npm install` had not run yet:\n"
    "   git add package-lock.json && git commit -m \"chore: add package-lock.json\" && git push"
)

# The `git add` line is built from _root_outputs.py rather than written out per
# variant (Issue #642): the paths it lists and the paths init.py produces used to
# be two hand-maintained lists, and an addition to one of them silently missing
# from the other is what broke every --quartz-pages repository's first Pages
# build (Issue #556).
_GIT_ADD_INDENT = "     "
_GIT_ADD_WIDTH = 96


def build_git_add(variant: str, vocab_cache_created: bool) -> str:
    """Render `git add <paths>`, wrapping with backslash continuations.

    The wrapping is cosmetic; `_root_outputs.git_add_paths()` owns which paths
    appear and in what order.
    """
    lines: list[str] = []
    current = "git add"
    for path in _root_outputs.git_add_paths(variant, vocab_cache_created=vocab_cache_created):
        candidate = f"{current} {path}"
        # `current == "git add"` is the only state that must never be flushed on its own:
        # a path longer than the width would otherwise produce a line holding just the prefix.
        if len(candidate) > _GIT_ADD_WIDTH and current != "git add":
            lines.append(current)
            current = _GIT_ADD_INDENT + path
        else:
            current = candidate
    lines.append(current)
    return " \\\n".join(lines)

_MERGE_STEP_PLAIN = "Merge to the main branch with /wikicommit-merge."
_MERGE_STEP_PAGES = (
    "Merge to the main branch with /wikicommit-merge (once merged to main,\n"
    "   GitHub Actions will automatically build with Quartz and publish to GitHub Pages)."
)

_README_STEP_WITH_URL = (
    "Consider adding a link to the published wiki in README.md (this is not done automatically —\n"
    "   README.md may already have its own structure that an automatic edit could disrupt):\n"
    "   📖 [View the wiki]({html_url})"
)
_README_STEP_NO_URL = (
    "Once you enable GitHub Pages manually (see the note above), consider adding a link to the\n"
    "   published wiki in README.md."
)

# Issue #558: init.py deliberately does not write a LICENSE file. A WikiCommit
# repository holds two different things — code (scripts, plugins) and content
# derived from third-party sources — and the content half has no single license
# to declare: one page can be CC BY-SA (a Wikipedia-derived page), another
# bound by a municipal site's own terms, another an ordinary all-rights-reserved
# paper that cannot be relicensed at all. Generating a single root LICENSE would
# purport to grant rights the operator does not hold. The per-page attribution
# (sources[].license, shown by the WikiCommitSources component) is what carries
# the legal weight; this step just makes sure the operator knows the decision is
# theirs to make. WikiCommit does not decide it for them.
#
# The README bullet is licensing layer 4 (Issue #645). Issue #282 settled that
# README.md is display-only — the agent never edits it — so the landing point for
# that layer can only be advice, and it is deliberately concrete (suggested wording
# the operator can paste) rather than a bare "consider documenting this". It mirrors
# _README_STEP_WITH_URL above, which already asks rather than writes, for the same
# reason. Layer 2 (site-wide) is not here: convert_wikilinks.py puts it on the
# generated root index and sources index, which need no operator action.
_LICENSING_STEP = (
    "Decide how this repository is licensed — nothing was generated for you (a WikiCommit repo\n"
    "   mixes code with content derived from third-party sources, and those sources' terms can\n"
    "   differ page by page, so no single LICENSE file would be correct). Two separate questions,\n"
    "   and one place to write the answer down:\n"
    "   • Code (`.wikicommit/scripts/`, `quartz-plugins/`, config): pick a license and add a\n"
    "     LICENSE file if you want one — this is the ordinary open-source choice.\n"
    "   • Content (`.wikicommit/entity/`): each page's terms follow the sources it was generated\n"
    "     from. Record each source's terms in the management file's `source.license` field; that\n"
    "     value is copied onto every page generated from it and shown next to that source on the\n"
    "     published site, together with a standing notice that the page adapts its sources.\n"
    "   • README.md: consider adding a short section saying the same two things, so that someone\n"
    "     who clones or browses the repository sees it before reaching a page. Nothing is written\n"
    "     for you here either — README.md is yours to edit. Something like: \"Code in this\n"
    "     repository and the wiki content it publishes are licensed separately. Page content is\n"
    "     derived from the sources listed on each page; terms differ per source and no single\n"
    "     license covers the wiki as a whole. See each page's sources for its terms.\"\n"
    "   WikiCommit records and displays what you tell it — it does not determine what a source's\n"
    "   terms are, nor whether they permit republishing. That judgment is yours."
)

_QUARTZ_ONLY_TRAILING_NOTE = (
    "Note: automatic GitHub Pages publishing was not set up (you did not opt into `--quartz-pages`),\n"
    "so the wiki stays local/preview-only for now — merges to main do not publish anywhere. To add\n"
    "automatic publishing later, re-run `wikicommit-init` and answer Y to the GitHub Pages\n"
    "confirmation, or manually copy\n"
    "`.claude/skills/wikicommit-init/scripts/templates/workflows/deploy.yml` to\n"
    "`.github/workflows/deploy.yml` and enable Settings → Pages → Source: GitHub Actions."
)

_PACKAGE_JSON_SKIPPED_WARNING = (
    "⚠️ package.json already existed in this repository, so WikiCommit's Quartz build scripts\n"
    '   ("build" / "preview") and devDependencies were not added to it (init.py never overwrites an\n'
    '   existing package.json). Merge the "scripts" and\n'
    '   "devDependencies" from .claude/skills/wikicommit-init/scripts/templates/package.json into\n'
    "   your package.json by hand before running /wikicommit-serve."
)

_PAGES_ENABLED = "✅ GitHub Pages enabled (Source: GitHub Actions)."
_PAGES_FALLBACK = (
    "⚠️ Could not enable GitHub Pages automatically. Enable it manually:\n"
    "   Settings → Pages → Source: GitHub Actions"
)

_ACTIONS_PR_PERMISSION_ENABLED = (
    '✅ "Allow GitHub Actions to create and approve pull requests" is enabled (needed for the\n'
    "   review-issue-close-sync.yml auto-merge flow, Issue #313)."
)
_ACTIONS_PR_PERMISSION_FALLBACK = (
    "⚠️ Could not confirm \"Allow GitHub Actions to create and approve pull requests\" is enabled.\n"
    "   Without it, review-issue-close-sync.yml's auto-merge step will fail (Issue #403) the first\n"
    "   time a reviewer closes a tracking Issue. Enable it manually:\n"
    "   Settings → Actions → General → Workflow permissions → check \"Allow GitHub Actions to\n"
    "   create and approve pull requests\""
)

_QUARTZ_STATUS_ANNOUNCEMENT = {
    "fully_set_up": "✅ Quartz v5 is already set up (npm install skipped).",
    "npm_install_completed_fully_set_up": "✅ npm install completed.",
    "npm_install_completed_submodule_pending": (
        "✅ npm install completed (top-level dependencies only — the Quartz v5 submodule has not "
        "been added yet)."
    ),
    "npm_install_failed_submodule_exists": None,
    "npm_install_failed_no_submodule": None,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--variant", required=True, choices=["none", "quartz_only", "quartz_pages"])
    parser.add_argument("--lychee-installed", action="store_true")
    parser.add_argument("--markitdown-installed", action="store_true")
    parser.add_argument("--actions-pr-permission-enabled", action="store_true")
    parser.add_argument("--package-json-skipped", action="store_true")
    parser.add_argument("--quartz-status", choices=QUARTZ_STATUSES)
    parser.add_argument("--install-plugins-status", choices=["ok", "failed"])
    parser.add_argument("--pages-html-url")
    parser.add_argument("--vocab-cache-created", action="store_true")
    return parser.parse_args()


def build_commit_step(variant: str, vocab_cache_created: bool) -> str:
    # .wikicommit/schemaorg-vocab.json (Issue #319) is committed like any other WikiCommit
    # output, but it is only ever created when a type-proposal step actually ran and hit the
    # network — listing it unconditionally would make this printed `git add` fail outright
    # on a pathspec that doesn't exist (Issue #490's obvious-type judgment is the first
    # wikicommit-init step able to create this file; wikicommit-generate/wikicommit-collect
    # created it before, but their output is committed later via wikicommit-merge, not here).
    # _root_outputs.py carries that condition, so it is passed through rather than handled here.
    git_add = build_git_add(variant, vocab_cache_created)
    if variant == "none":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_NONE_EXTRA_FILES,
            git_add=git_add,
            commit_msg="chore: add WikiCommit foundational files",
        )
    if variant == "quartz_only":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_QUARTZ_ONLY_EXTRA_FILES,
            git_add=git_add,
            commit_msg="chore: add WikiCommit foundational files and Quartz v5 local build config",
        ) + _PACKAGE_LOCK_NOTE
    return _COMMIT_STEP_INTRO.format(
        extra_files=_QUARTZ_PAGES_EXTRA_FILES,
        git_add=git_add,
        commit_msg="chore: add WikiCommit foundational files and Quartz v5 publishing config",
    ) + _PACKAGE_LOCK_NOTE


def build_quartz_setup_step(args: argparse.Namespace) -> str | None:
    """Returns None when the step should be omitted from the numbered list entirely."""
    if args.package_json_skipped:
        # init.py step 3.e (check_quartz_setup.py) never ran in this case; keep both
        # lines unchanged regardless — git submodule add / npm install don't depend on
        # the preview/build scripts being present in package.json.
        return _QUARTZ_SETUP_FULL
    status = args.quartz_status
    if status in ("fully_set_up", "npm_install_completed_fully_set_up"):
        # check_quartz_setup.py already attempted `npm run install-plugins` for us
        # (quartz/ exists in both of these statuses). Only remind the user if that
        # attempt failed — otherwise there is nothing left to do (Issue #380).
        return None if args.install_plugins_status == "ok" else _INSTALL_PLUGINS_STEP
    if status == "npm_install_failed_submodule_exists":
        # quartz/ exists here too, so the same auto-attempt already ran; drop the
        # redundant `npm run install-plugins` line if it already succeeded.
        return _QUARTZ_SETUP_NPM_INSTALL_ONLY if args.install_plugins_status == "ok" else _QUARTZ_SETUP_NPM_ONLY
    # npm_install_completed_submodule_pending, npm_install_failed_no_submodule, or unset
    return _QUARTZ_SETUP_FULL


def build_announcements(args: argparse.Namespace) -> list[str]:
    announcements = []
    if args.lychee_installed:
        announcements.append("✅ lychee is installed.")
    if args.markitdown_installed:
        announcements.append("✅ markitdown is installed.")
    # Unconditional (unlike the block below): review-issue-close-sync.yml ships
    # regardless of --variant, so this setting matters regardless of --variant too.
    announcements.append(
        _ACTIONS_PR_PERMISSION_ENABLED if args.actions_pr_permission_enabled else _ACTIONS_PR_PERMISSION_FALLBACK
    )
    if args.variant != "none":
        if args.variant == "quartz_pages":
            announcements.append(_PAGES_ENABLED if args.pages_html_url else _PAGES_FALLBACK)
        if args.package_json_skipped:
            announcements.append(_PACKAGE_JSON_SKIPPED_WARNING)
        else:
            status_announcement = _QUARTZ_STATUS_ANNOUNCEMENT.get(args.quartz_status)
            if status_announcement:
                announcements.append(status_announcement)
            if args.install_plugins_status == "ok":
                announcements.append("✅ Quartz community plugins installed (npm run install-plugins).")
    return announcements


def build_steps(args: argparse.Namespace) -> list[str]:
    steps: list[str] = []
    if args.variant != "none":
        quartz_setup_step = build_quartz_setup_step(args)
        if quartz_setup_step is not None:
            steps.append(quartz_setup_step)
        deploy_suffix = ", without waiting for a GitHub Pages deploy" if args.variant == "quartz_pages" else ""
        steps.append(_PREVIEW_STEP.format(deploy_suffix=deploy_suffix))
    if not args.lychee_installed:
        steps.append(_LYCHEE_STEP)
    if not args.markitdown_installed:
        steps.append(_MARKITDOWN_STEP)
    steps.append(build_commit_step(args.variant, args.vocab_cache_created))
    steps.append(_REGISTER_STEP)
    steps.append(_MERGE_STEP_PAGES if args.variant == "quartz_pages" else _MERGE_STEP_PLAIN)
    if args.variant == "quartz_pages":
        if args.pages_html_url:
            steps.append(_README_STEP_WITH_URL.format(html_url=args.pages_html_url))
        else:
            steps.append(_README_STEP_NO_URL)
    steps.append(_LICENSING_STEP)
    return steps


def render(args: argparse.Namespace) -> str:
    lines: list[str] = []
    lines.extend(build_announcements(args))
    if lines:
        lines.append("")
    lines.append("✅ WikiCommit initialization complete.")
    lines.append("")
    lines.append("Next steps:")
    for i, step in enumerate(build_steps(args), start=1):
        lines.append(f"{i}. {step}")
        lines.append("")
    if args.variant == "quartz_only":
        lines.append(_QUARTZ_ONLY_TRAILING_NOTE)
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    sys.stdout.write(render(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
