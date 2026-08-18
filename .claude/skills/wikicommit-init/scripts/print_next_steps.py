#!/usr/bin/env python3
"""Render wikicommit-init step 3's "next steps" guidance text (Issue #350).

Before this script existed, SKILL.md hardcoded three near-identical copies of this
guidance (one per --quartz / --quartz-pages combination), differing only in a handful
of lines (the git add file list, the commit message, a couple of sentences). That
duplication pushed SKILL.md past the 500-line recommended limit
(dev/scripts/check_skill_md_lines.py) even though the choice of which lines to print
is fully deterministic given the flags the agent already computed in steps 2-3
(docs/DesignDoc-skills.md section 11.5 — deterministic, repetitive text belongs in a
script, not duplicated prose). The agent computes the flags (variant chosen in
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
    '   (Issue #339 — backs the wikicommit-banner "Report an issue" link, which otherwise silently\n'
    "   no-ops), and the root-level publishing configuration files "
)
_QUARTZ_ONLY_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (Issue #313 — needed for the tracking-Issue\n"
    "   review flow, regardless of the Quartz choice), `.github/ISSUE_TEMPLATE/report.md`\n"
    '   (Issue #339 — backs the wikicommit-banner "Report an issue" link, which otherwise silently\n'
    "   no-ops), and the root-level local-build configuration files "
)
_NONE_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (Issue #313 — needed for the tracking-Issue\n"
    "   review flow), and the quality gate configuration files "
)

_VOCAB_CACHE_FILE = ".wikicommit/schemaorg-vocab.json"

_GIT_ADD_NONE = (
    "git add .claude .gitignore .wikicommit/config.yml .wikicommit/schema .wikicommit/scripts \\\n"
    "     .wikicommit/entity .wikicommit/source \\\n"
    "     .lychee.toml .markdownlint.json .github/workflows/review-issue-close-sync.yml"
)
_GIT_ADD_QUARTZ_ONLY = (
    "git add .claude .gitignore .wikicommit/config.yml .wikicommit/schema .wikicommit/scripts \\\n"
    "     .wikicommit/entity .wikicommit/source \\\n"
    "     .lychee.toml .markdownlint.json quartz.config.yaml package.json prebuild-symlinks.cjs \\\n"
    "     repair-plugin-builds.cjs \\\n"
    "     .github/workflows/review-issue-close-sync.yml \\\n"
    "     .github/ISSUE_TEMPLATE/report.md \\\n"
    "     quartz-plugins .gitmodules quartz"
)
_GIT_ADD_QUARTZ_PAGES = (
    "git add .claude .gitignore .wikicommit/config.yml .wikicommit/schema .wikicommit/scripts \\\n"
    "     .wikicommit/entity .wikicommit/source \\\n"
    "     .lychee.toml .markdownlint.json quartz.config.yaml package.json prebuild-symlinks.cjs \\\n"
    "     repair-plugin-builds.cjs \\\n"
    "     .github/workflows/deploy.yml .github/workflows/review-issue-close-sync.yml \\\n"
    "     .github/ISSUE_TEMPLATE/report.md \\\n"
    "     quartz-plugins .gitmodules quartz"
)

_MERGE_STEP_PLAIN = "Merge to the main branch with /wikicommit-merge."
_MERGE_STEP_PAGES = (
    "Merge to the main branch with /wikicommit-merge (once merged to main,\n"
    "   GitHub Actions will automatically build with Quartz and publish to GitHub Pages)."
)

_README_STEP_WITH_URL = (
    "Consider adding a link to the published wiki in README.md (this is not done automatically —\n"
    "   README.md may already have its own structure that an automatic edit could disrupt, see\n"
    "   docs/DesignDoc-data.md §3.1):\n"
    "   📖 [View the wiki]({html_url})"
)
_README_STEP_NO_URL = (
    "Once you enable GitHub Pages manually (see the note above), consider adding a link to the\n"
    "   published wiki in README.md."
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
    "   existing package.json — see docs/DesignDoc-data.md §3.1). Merge the \"scripts\" and\n"
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


def _with_vocab_cache(git_add: str, vocab_cache_created: bool) -> str:
    # .wikicommit/schemaorg-vocab.json (Issue #319) is committed like any other WikiCommit
    # output, but it is only ever created when a type-proposal step actually ran and hit the
    # network — appending it unconditionally would make this printed `git add` fail outright
    # on a pathspec that doesn't exist (Issue #490's obvious-type judgment is the first
    # wikicommit-init step able to create this file; wikicommit-generate/wikicommit-collect
    # created it before, but their output is committed later via wikicommit-merge, not here).
    if not vocab_cache_created:
        return git_add
    return git_add + f" \\\n     {_VOCAB_CACHE_FILE}"


def build_commit_step(variant: str, vocab_cache_created: bool) -> str:
    if variant == "none":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_NONE_EXTRA_FILES,
            git_add=_with_vocab_cache(_GIT_ADD_NONE, vocab_cache_created),
            commit_msg="chore: add WikiCommit foundational files",
        )
    if variant == "quartz_only":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_QUARTZ_ONLY_EXTRA_FILES,
            git_add=_with_vocab_cache(_GIT_ADD_QUARTZ_ONLY, vocab_cache_created),
            commit_msg="chore: add WikiCommit foundational files and Quartz v5 local build config",
        )
    return _COMMIT_STEP_INTRO.format(
        extra_files=_QUARTZ_PAGES_EXTRA_FILES,
        git_add=_with_vocab_cache(_GIT_ADD_QUARTZ_PAGES, vocab_cache_created),
        commit_msg="chore: add WikiCommit foundational files and Quartz v5 publishing config",
    )


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
