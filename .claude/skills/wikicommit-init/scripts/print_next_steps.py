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
import textwrap
from pathlib import Path

import _root_outputs


def _templates_display() -> str:
    """Where this Skill's templates are, as the reader would type it from the repository root.

    Taken from this file's own location rather than written as `.claude/skills/...`:
    the Skills may be installed under `.agents/skills/` instead (Issue #1021), and a path
    printed for a human to copy has to be the one that exists.
    """
    templates = Path(__file__).resolve().parent / "templates"
    try:
        return templates.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return templates.as_posix()


_TEMPLATES = _templates_display()

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
    "   prebuild-symlinks.cjs, which only handles quartz/content and\n"
    "   quartz/quartz.config.yaml and needs no such privilege (directory junction + file-copy\n"
    "   fallback).\n"
    "\n"
    "   On every platform, building writes into the quartz/ submodule: quartz/content and\n"
    "   quartz/quartz.config.yaml, the installed plugins, and a change to the tracked\n"
    "   quartz/package-lock.json (from the `npm install` that `postinstall` runs there).\n"
    "   This is WikiCommit's build, not your editing, and it never reaches your history —\n"
    "   `git add quartz` records only the submodule's commit pointer. The one time it\n"
    "   matters is updating Quartz itself: `git pull` inside quartz/ stops on that\n"
    "   package-lock.json change. .wikicommit/guides/updating-the-quartz-submodule.md has\n"
    "   the steps (updating is optional; the published site keeps the recorded commit)."
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

# The intro no longer tells the user these are theirs *alone* to run (Issue #843). Both reasons
# it gave for that were already broken. `.wikicommit/schema/` is written by init.py, which the
# agent launches, and step 3's obvious-type judgment has the agent write a schema file directly
# (Issue #490) — what is forbidden there is *authoring*, not committing what one just authored.
# And `main` is not the invariant either: CLAUDE.md's rule is that an LLM's commits go through a
# PR, and `wikicommit-merge` branches, commits, pushes and squash merges under exactly that rule.
# The foundational commit has no PR route available (init is often a repository's first commit,
# so there may be no base branch and no remote), and its content carries no LLM-authored
# knowledge — deterministic template expansion plus type files the user approved with Enter. So
# the agent offers to run them, asking first with the same strength the `--quartz-pages` Pages
# activation asks, and this printed guidance stays exactly as it is for the decline /
# non-interactive / failure paths (Issue #86's remedy is not weakened).
#
# The wording has to hold in all of those paths, including when this script is re-run standalone
# later to reprint the guidance, so it states what `/wikicommit-init` does rather than assuming
# who is reading it or what they already answered. That is why it reads "run them yourself
# unless ... you accepted" rather than "it asks once": SKILL.md also withholds the offer in two
# cases that are not a decline — a repository that already had its own `.gitignore` (skipped
# outright), and a still-pending "Set up Quartz v5" step, which is every first --quartz run
# (deferred until the user finishes that step, after which the guidance is reprinted without it
# and the offer applies to the reprint — Issue #865). So promising a prompt would still be false
# on a standalone re-run of this script, and on the Quartz path it would be premature rather than
# wrong; the wording has to hold for a reader of either.
_COMMIT_STEP_INTRO = (
    'Commit the generated foundational files (`/wikicommit-merge` only targets\n'
    '   "changes" under `.wikicommit/entity/` and `.wikicommit/source/`, so\n'
    "   `.claude/skills/` (plus `.agents/`, which holds the Skills themselves whenever\n"
    "   `.claude/skills/` is a tree of symlinks into it), `.wikicommit/config.yml`,\n"
    "   `.wikicommit/schema/`, `.wikicommit/scripts/`, `.wikicommit/entity/`,\n"
    "   `.wikicommit/source/`,\n"
    "   {extra_files}will never get committed anywhere\n"
    "   in the pipeline unless committed here. Run them yourself unless `/wikicommit-init` offered\n"
    "   to run them for you and you accepted: it asks at most once, only where it can stage exactly\n"
    "   its own output, and it says so whenever it is leaving them to you. `-A` is the right\n"
    "   default in a repository created for this wiki; if WikiCommit was added to a repository\n"
    "   that already had files of its own, read the note under the commands before running it:\n"
    "   git add -A\n"
    '   git commit -m "{commit_msg}"\n'
    "   git push"
    "{selective_note}"
)

# `git add -A` rather than the per-path list this used to print (Issue #842). `.gitignore`
# is written by this same run — and extended with a Quartz section under --quartz — so in a
# repository created for this wiki the two stage exactly the same set. What differs is the
# failure mode: `git add` aborts the *whole* command on a pathspec that does not exist
# (measured: exit 128, zero files staged), and the printed list carries two paths nobody
# generates — `.gitmodules` and `quartz`, which the user creates with `git submodule add` in
# an earlier step. Copying the printed commands in order, or coming back to Quartz later,
# therefore took the entire foundational commit down with it, which is the state Issue #86
# added this step to prevent. The list is kept below for the one case where it is actually
# the right tool.
#
# "the two stage the same set" holds only where `.gitignore` actually carries WikiCommit's
# patterns. It carries update="review" in _root_outputs.py, so init.py skips it outright when
# the repository already has one (only the Quartz section is appended), and none of
# node_modules/, .wikicommit/.cache/ or .wikicommit/run/ is then ignored — `-A` after the
# guidance's own `npm install` step would commit node_modules/ wholesale.
#
# This used to be stated as prose covering both cases, because "print_next_steps.py is handed
# flags, not the repository, and there is no --gitignore-skipped flag to condition on". That
# reasoning had the same false premise the foundational-commit offer had (Issue #873): the
# question is what is *in* the file, not who wrote it, and that is readable from disk without
# any flag. This script runs after init.py, so the `.gitignore` it reads is the final one —
# Quartz section included. Both callers now ask _root_outputs.missing_gitignore_patterns(),
# so the note and the offer cannot disagree about the same repository — provided they are given
# the same one, which is why --repo-root exists here too rather than assuming the working
# directory is the repository init.py wrote to.
_SELECTIVE_ADD_NOTE_READY = (
    "\n\n"
    "   `-A` stages everything not excluded by `.gitignore`, and this repository's `.gitignore`\n"
    "   already carries WikiCommit's patterns — node_modules/, .wikicommit/.cache/ and\n"
    "   .wikicommit/run/ among them — so that is WikiCommit's own output and nothing else.\n"
    "   If this repository also has files of its own, `-A` stages those untracked files and any\n"
    "   uncommitted change to a tracked one too, so check `git status --short` first. Or stage\n"
    "   only what this run produced:\n"
    "   {git_add}{absent_caveat}"
)

_SELECTIVE_ADD_NOTE_MISSING = (
    "\n\n"
    "   `-A` stages everything not excluded by `.gitignore`, and this repository's `.gitignore`\n"
    "   does not yet ignore\n"
    "{missing}\n"
    "   An existing `.gitignore` is never overwritten (only a Quartz section is appended to it),\n"
    "   so add those patterns before running `-A` — otherwise they go into the commit, and the\n"
    "   guidance's own `npm install` step above means node_modules/ would go in wholesale.\n"
    "   `-A` also stages this repository's own untracked files and any uncommitted change to a\n"
    "   tracked one, so check `git status --short` first either way. Or stage only what this run\n"
    "   produced:\n"
    "   {git_add}{absent_caveat}"
)

# The selective list carries paths that belong in the first commit but are not always on
# disk, and `git add` still aborts on a pathspec that does not exist. The default no longer
# does, but the note above sends exactly the repository shape most likely to be missing one
# down this path, so say it here rather than leave them to interpret exit 128 —
# `wikicommit-update` prints the same caveat for the same reason.
#
# Two kinds of path, one sentence: `.gitmodules` / `quartz` are the user's own
# `git submodule add`, deferred or skipped; `.agents` / `skills-lock.json` depend on how
# `npx skills add` placed the Skills, which this run never observed (Issue #948). The wording
# is generic because the reader does not need the reason — they need to know to drop what
# they do not have. Derived from _root_outputs.py so that adding another such path carries
# here without a second list.
#
# Wrapped at render time rather than carrying its own newlines: the list grows whenever an
# entry gains `may_be_absent`, and a hard-coded break placed for two paths overran to 124
# columns as soon as there were four — in guidance every other line of which is held to
# roughly this width. Same reason `build_selective_add_note()` fills the `missing` list.
_ABSENT_PATHSPEC_CAVEAT = (
    "(drop any of {paths} this repository does not have — `git add` aborts on a "
    "pathspec that does not exist and stages nothing.)"
)


def build_selective_add_note(
    variant: str, vocab_cache_created: bool, repo_root: Path | None = None, readme_created: bool = False
) -> str:
    """The note under the printed `git add -A`, in whichever of its two shapes applies.

    Reads the repository's `.gitignore` rather than taking a "did this run write it" flag, for
    the reason in the comment above the two templates: what matters is which patterns are in
    the file, and this script runs after init.py has finished writing it. `repo_root` says
    *which* repository — it has to be the one init.py was pointed at, not whatever the working
    directory happens to be, or the note and the offer answer about different files.
    """
    try:
        missing = _root_outputs.missing_gitignore_patterns(
            repo_root if repo_root is not None else Path.cwd(), variant
        )
    except OSError:
        # The templates this is read from ship alongside this script, so failing to read them
        # means the installation is broken rather than that the repository is fine. Print the
        # cautious note instead of the confident one — this script always exits 0, and a note
        # that overstates what `.gitignore` covers is the one outcome it must not produce.
        missing = ["WikiCommit's own ignore patterns (the shipped template could not be read)"]
    template = _SELECTIVE_ADD_NOTE_MISSING if missing else _SELECTIVE_ADD_NOTE_READY
    return template.format(
        git_add=build_git_add(variant, vocab_cache_created, readme_created),
        absent_caveat=build_absent_pathspec_caveat(variant),
        # Wrapped rather than joined into one line: a repository whose `.gitignore` is missing
        # every pattern lists ten or more of them, and every other line of this guidance is
        # hand-wrapped to roughly this width.
        missing=textwrap.fill(
            ", ".join(missing) + ".",
            width=95,
            initial_indent="     ",
            subsequent_indent="     ",
            break_long_words=False,
            break_on_hyphens=False,
        ),
    )


def build_absent_pathspec_caveat(variant: str) -> str:
    paths = [
        entry.path
        for entry in _root_outputs.for_variant(variant)
        if entry.may_be_absent and entry.in_git_add
    ]
    if not paths:
        return ""
    return "\n\n" + textwrap.fill(
        _ABSENT_PATHSPEC_CAVEAT.format(paths=", ".join(f"`{path}`" for path in paths)),
        width=95,
        initial_indent="   ",
        subsequent_indent="   ",
        break_long_words=False,
        break_on_hyphens=False,
    )

_QUARTZ_PAGES_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (needed for the tracking-Issue\n"
    "   review flow, regardless of the Quartz choice), `.github/ISSUE_TEMPLATE/report.md`\n"
    '   (backs the wikicommit-banner report link, which otherwise silently\n'
    "   no-ops), and the root-level publishing configuration files "
)
_QUARTZ_ONLY_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (needed for the tracking-Issue\n"
    "   review flow, regardless of the Quartz choice), `.github/ISSUE_TEMPLATE/report.md`\n"
    '   (backs the wikicommit-banner report link, which otherwise silently\n'
    "   no-ops), and the root-level local-build configuration files "
)
_NONE_EXTRA_FILES = (
    "`.github/workflows/review-issue-close-sync.yml` (needed for the tracking-Issue\n"
    "   review flow), and the quality gate configuration files "
)

# package-lock.json は `_root_outputs.py` 上 `in_git_add=False` であり、上の選択的な列挙には
# 含まれない（Issue #556 の対応方針3の結論）。init.py の生成物ではなく Quartz セットアップ手順の
# `npm install` の副産物であり、npm install が失敗した場合・ユーザーがその手順を飛ばした場合には
# 存在しないため、列挙に足すと `git add` の abort-on-missing で基盤コミットそのものが落ちる。
# Issue #842 で既定が `git add -A` になったため、**既定の経路ではこの注記は不要になった** —
# 存在すれば -A が拾い、存在しなければ何も起きない。それでも残すのは 2 つの理由による:
# (1) 選択的な列挙を使うユーザーには依然として漏れる、(2) なぜコミットする価値があるのかは
# -A では伝わらない。`in_git_add=False` 自体も残す — あれは「これは決定であって漏れではない」を
# 記録するフィールドであり（Issue #556 の再発防止）、削るとその記録が失われる。
# 案内文からは手順番号（「step 1 の npm install」等）を参照しない: build_quartz_setup_step が
# None / _INSTALL_PLUGINS_STEP を返す分岐では npm install 手順そのものが番号付きリストから
# 消え、番号がずれる。--quartz 単体（deploy.yml なし）でも成り立つ書き方にしておく。
_PACKAGE_LOCK_NOTE = (
    "\n\n"
    "   The root `package-lock.json` is worth committing too once `npm install` has created one —\n"
    "   it pins the dependency versions a fresh clone resolves, including the GitHub Pages build\n"
    "   workflow if this repository has (or later enables) one. `git add -A` above picks it up on\n"
    "   its own; if you staged selectively instead, add it by hand:\n"
    "   git add package-lock.json"
)

# The `git add` line is built from _root_outputs.py rather than written out per
# variant (Issue #642): the paths it lists and the paths init.py produces used to
# be two hand-maintained lists, and an addition to one of them silently missing
# from the other is what broke every --quartz-pages repository's first Pages
# build (Issue #556).
_GIT_ADD_INDENT = "     "
_GIT_ADD_WIDTH = 96


def build_git_add(variant: str, vocab_cache_created: bool, readme_created: bool = False) -> str:
    """Render `git add <paths>`, wrapping with backslash continuations.

    The wrapping is cosmetic; `_root_outputs.git_add_paths()` owns which paths
    appear and in what order.
    """
    lines: list[str] = []
    current = "git add"
    for path in _root_outputs.git_add_paths(
        variant, vocab_cache_created=vocab_cache_created, readme_created=readme_created
    ):
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
# The only place a human reliably reads right after init, which is why the pointer to the
# guides shelf goes here (Issue #846). Shown for every variant since Issue #867 added a guide
# that has nothing to do with Quartz: the condition that used to gate this existed only
# because the single guide then on the shelf was about a Quartz plugin, and a line nobody can
# act on teaches people to skim the list. Adding a guide means naming it here — this string is
# not generated from the directory, and `tests/test_guides_tree.py` fails until it matches.
_GUIDES_STEP = (
    "Longer how-to walkthroughs live in `.wikicommit/guides/` — one per task, written for a\n"
    "   person rather than for an agent, and refreshed by later inits. Three so far:\n"
    "   `applying-entity-policy-to-existing-pages.md` (what to do after changing\n"
    "   `.wikicommit/entity-policy.md`, since the policy is read only while a page is being\n"
    "   generated), `enabling-comments.md` (turning on the giscus comment box, which is off\n"
    "   by default — `--quartz` wikis only) and `updating-the-quartz-submodule.md` (moving\n"
    "   `quartz/` to a newer Quartz — optional, and `--quartz` wikis only)."
)

_LICENSING_STEP_HEAD = (
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
)
_LICENSING_STEP_TAIL = (
    "   WikiCommit records and displays what you tell it — it does not determine what a source's\n"
    "   terms are, nor whether they permit republishing. That judgment is yours."
)


def build_licensing_step(readme_created: bool) -> str:
    """The licensing step, with the README bullet only when the README was already there.

    When init created README.md (Issue #1034) it wrote the licensing section itself, from the
    same `_root_outputs.README_LICENSE_TEXT` this bullet quotes — so offering it again would
    say the same thing twice. When the README was already there, init did not touch it
    (Issue #282), and this bullet is still the only place that wording reaches the user.
    """
    if readme_created:
        return _LICENSING_STEP_HEAD + _LICENSING_STEP_TAIL
    readme_bullet = textwrap.fill(
        "• README.md: consider adding a short section saying the same two things, so that "
        "someone who clones or browses the repository sees it before reaching a page. Nothing "
        "is written for you here either — README.md is yours to edit. Something like: "
        f"\"{_root_outputs.README_LICENSE_TEXT}\"",
        width=95,
        initial_indent="   ",
        subsequent_indent="     ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return _LICENSING_STEP_HEAD + readme_bullet + "\n" + _LICENSING_STEP_TAIL

_QUARTZ_ONLY_TRAILING_NOTE = (
    "Note: automatic GitHub Pages publishing was not set up (you did not opt into `--quartz-pages`),\n"
    "so the wiki stays local/preview-only for now — merges to main do not publish anywhere. To add\n"
    "automatic publishing later, re-run `wikicommit-init` and answer Y to the GitHub Pages\n"
    "confirmation, or manually copy\n"
    f"`{_TEMPLATES}/workflows/deploy.yml` to\n"
    "`.github/workflows/deploy.yml` and enable Settings → Pages → Source: GitHub Actions."
)

_PACKAGE_JSON_SKIPPED_WARNING = (
    "⚠️ package.json already existed in this repository, so WikiCommit's Quartz build scripts\n"
    '   ("build" / "preview") and devDependencies were not added to it (init.py never overwrites an\n'
    '   existing package.json). Merge the "scripts" and\n'
    f'   "devDependencies" from {_TEMPLATES}/package.json into\n'
    "   your package.json by hand before running /wikicommit-serve."
)

_PAGES_ENABLED = "✅ GitHub Pages enabled (Source: GitHub Actions)."
_PAGES_FALLBACK = (
    "⚠️ Could not enable GitHub Pages automatically. Enable it manually:\n"
    "   Settings → Pages → Source: GitHub Actions"
)

_ACTIONS_PR_PERMISSION_ENABLED = (
    '✅ "Allow GitHub Actions to create and approve pull requests" is enabled (needed for the\n'
    "   review-issue-close-sync.yml auto-merge flow)."
)
_ACTIONS_PR_PERMISSION_FALLBACK = (
    "⚠️ Could not confirm \"Allow GitHub Actions to create and approve pull requests\" is enabled.\n"
    "   Without it, review-issue-close-sync.yml's auto-merge step will fail the first\n"
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
    # Pass when init.py printed `CREATED: README.md` (Issue #1034). That README already
    # carries the licensing section and, under --quartz-pages, the published-site link, so the
    # guidance that suggests adding them is dropped; and the selective `git add` list names
    # README.md only then — a README that was already there may hold the user's own edits.
    parser.add_argument("--readme-created", action="store_true")
    # The repository this guidance is about. init.py takes the same flag, and the note under
    # the printed `git add -A` now reads that repository's `.gitignore` — so if the two are
    # handed different roots they answer about different files, which is exactly the
    # disagreement sharing missing_gitignore_patterns() was meant to rule out. Defaults to the
    # working directory, which is what init.py's own --repo-root defaults to.
    parser.add_argument("--repo-root", default=".")
    return parser.parse_args()


def build_commit_step(
    variant: str, vocab_cache_created: bool, repo_root: Path | None = None, readme_created: bool = False
) -> str:
    # .wikicommit/schemaorg-vocab.json (Issue #319) is committed like any other WikiCommit
    # output, but it is only ever created when a type-proposal step actually ran and hit the
    # network — listing it unconditionally would make this printed `git add` fail outright
    # on a pathspec that doesn't exist (Issue #490's obvious-type judgment is the first
    # wikicommit-init step able to create this file; wikicommit-generate/wikicommit-collect
    # created it before, but their output is committed later via wikicommit-merge, not here).
    # _root_outputs.py carries that condition, so it is passed through rather than handled here.
    # Since Issue #842 the condition only governs the selective fallback list below; the default
    # `git add -A` needs no such special case, because a file that is not there is simply not staged.
    selective_note = build_selective_add_note(variant, vocab_cache_created, repo_root, readme_created)
    if variant == "none":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_NONE_EXTRA_FILES,
            selective_note=selective_note,
            commit_msg="chore: add WikiCommit foundational files",
        )
    if variant == "quartz_only":
        return _COMMIT_STEP_INTRO.format(
            extra_files=_QUARTZ_ONLY_EXTRA_FILES,
            selective_note=selective_note,
            commit_msg="chore: add WikiCommit foundational files and Quartz v5 local build config",
        ) + _PACKAGE_LOCK_NOTE
    return _COMMIT_STEP_INTRO.format(
        extra_files=_QUARTZ_PAGES_EXTRA_FILES,
        selective_note=selective_note,
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


# The steps below name Skills the way Claude Code invokes them (`/wikicommit-…`). Codex
# invokes a Skill with `$` instead (`/skills` there only opens the list), so the one
# place this guidance reaches a person says so once, rather than every step carrying
# two spellings (Issue #1015).
_INVOCATION_NOTE = "(Commands below are written /wikicommit-…; in Codex, type $wikicommit-… instead.)"


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
    steps.append(
        build_commit_step(args.variant, args.vocab_cache_created, Path(args.repo_root), args.readme_created)
    )
    steps.append(_REGISTER_STEP)
    steps.append(_MERGE_STEP_PAGES if args.variant == "quartz_pages" else _MERGE_STEP_PLAIN)
    # A README init created in this run already carries the link when a URL was obtained, so
    # suggesting it again would repeat it. Without a URL, `--finish-readme` removed the marker and
    # the README has no link — the "once you enable Pages manually" reminder is still the only
    # place the user learns to add one, so it stays regardless of who wrote the README.
    if args.variant == "quartz_pages":
        if args.pages_html_url:
            if not args.readme_created:
                steps.append(_README_STEP_WITH_URL.format(html_url=args.pages_html_url))
        else:
            steps.append(_README_STEP_NO_URL)
    steps.append(_GUIDES_STEP)
    steps.append(build_licensing_step(args.readme_created))
    return steps


def render(args: argparse.Namespace) -> str:
    lines: list[str] = []
    lines.extend(build_announcements(args))
    if lines:
        lines.append("")
    lines.append("✅ WikiCommit initialization complete.")
    lines.append("")
    lines.append("Next steps:")
    lines.append(_INVOCATION_NOTE)
    lines.append("")
    for i, step in enumerate(build_steps(args), start=1):
        prefix = f"{i}. "
        # Every step embeds its own 3-space continuation indent, which lines up under
        # `"N. "` only while N is a single digit. Issue #846 made a ten-step list
        # reachable for the first time (quartz_pages with neither lychee nor markitdown
        # installed), so pad the extra column here rather than restating the indent in
        # every step string. Blank lines are left alone so padding never becomes
        # trailing whitespace.
        head, *rest = step.split("\n")
        if len(prefix) > 3 and rest:
            pad = " " * (len(prefix) - 3)
            step = "\n".join([head] + [pad + line if line else line for line in rest])
        lines.append(prefix + step)
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
