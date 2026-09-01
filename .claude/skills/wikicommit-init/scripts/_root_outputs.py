#!/usr/bin/env python3
"""The one list of what a freshly initialized repository has to commit (Issue #642).

`init.py` writes these files and `print_next_steps.py` tells the user to
`git add` them. Those were two independently hand-maintained lists (three,
counting the prose in SKILL.md), and the failure mode is not hypothetical:
`install-local-plugins.cjs` was added to `init.py` alone (Issue #434) and left
out of the guidance, so every repository initialized with `--quartz
--quartz-pages` failed its first GitHub Pages build with a `postinstall`
MODULE_NOT_FOUND (Issue #556 — reproduced in two pilots). Issue #556 added a
test that *detects* that drift; this module removes the second list instead, so
adding a root-level output is one edit rather than two or three.

Three kinds of entry do not fit "init.py writes it, the user commits it", and
each needs to stay expressible here rather than being special-cased at the call
site:

  - `.gitmodules` and `quartz` are in the guidance but nobody generates them —
    the user runs `git submodule add` (origin `submodule`). A test that walks
    this list has to know not to expect them on disk.
  - `.wikicommit/schemaorg-vocab.json` exists only when a type-proposal step
    actually hit the network (`condition="vocab_cache"`). `git add` aborts on a
    pathspec that does not exist, which would take the whole foundational commit
    down with it, so it is appended only when the caller says it was created.
  - `package-lock.json` is a side effect of `npm install` (origin `npm`), and is
    deliberately *not* in the `git add` line for that same abort-on-missing
    reason — `print_next_steps.py` guides it as its own command (Issue #556).
    `in_git_add=False` records that this is a decision, not an omission.

`.claude/` is listed too though `install.sh` (not `init.py`) puts it there: the
list describes what the first commit must contain, and that is the question the
guidance answers.
"""

from dataclasses import dataclass

VARIANTS = ("none", "quartz_only", "quartz_pages")

# Who puts the path there. Free strings would let a typo (`"Init"`) silently drop an entry
# from plain_copies() while git_add_paths() keeps listing it — the drift this module exists
# to remove — so the accepted values are enumerated and checked.
ORIGINS = ("init", "install", "submodule", "npm")

# When the path exists. Each value needs its own answer in git_add_paths(); a new one must be
# wired up there rather than silently falling through to whatever the last branch tests.
CONDITIONS = ("always", "vocab_cache")

# Every variant; spelled out rather than defaulted so that adding an entry is a
# deliberate choice about which initializations it belongs to.
ALL = frozenset(VARIANTS)
QUARTZ = frozenset(("quartz_only", "quartz_pages"))
PAGES_ONLY = frozenset(("quartz_pages",))


@dataclass(frozen=True)
class RootOutput:
    """One path a freshly initialized repository is expected to commit."""

    path: str
    """Repository-relative path, exactly as it appears in the `git add` line."""

    variants: frozenset
    """Which `--variant` values include this path."""

    origin: str
    """Who puts it there; one of ORIGINS: `init` (init.py), `install` (install.sh),
    `submodule` (the user's own `git submodule add`), or `npm` (`npm install`)."""

    template: str | None = None
    """Path under `templates/` for entries init.py produces by a plain copy, so
    it can drive those copies from this list. `None` means either a different
    origin, or generation that is not a plain copy (a directory tree, a
    placeholder substitution, a created-and-gitkeeped directory) and therefore
    stays written out in init.py."""

    condition: str = "always"
    """One of CONDITIONS: `always`, or `vocab_cache` for the path that exists only
    when a type-proposal step created the Schema.org vocabulary cache."""

    in_git_add: bool = True
    """False for a path the guidance covers with its own separate command."""


# Order is the order the `git add` line lists them in.
ROOT_OUTPUTS: tuple[RootOutput, ...] = (
    RootOutput(".claude", ALL, origin="install"),
    RootOutput(".gitignore", ALL, origin="init", template=".gitignore"),
    # Placeholder substitution (version/targets/primary_lang/theme), not a copy.
    RootOutput(".wikicommit/config.yml", ALL, origin="init"),
    # Written by hand after init, and the Skills only ever append to its `rejected:`
    # list, so a re-run must never overwrite it (init.py copies every entry here with
    # always_skip_existing=True, the same protection .lychee.toml gets).
    RootOutput(".wikicommit/source-policy.md", ALL, origin="init", template="source-policy.md"),
    # Same shape and the same protection as source-policy.md, one axis over: that file
    # says which sources come in, this one says whether an entity may be written about
    # at all (Issue #667). Hand-edited prose, so a re-run must never overwrite it.
    RootOutput(".wikicommit/entity-policy.md", ALL, origin="init", template="entity-policy.md"),
    # Directory trees and created-with-.gitkeep directories.
    RootOutput(".wikicommit/schema", ALL, origin="init"),
    RootOutput(".wikicommit/scripts", ALL, origin="init"),
    RootOutput(".wikicommit/entity", ALL, origin="init"),
    # Second-order pages, grounded in this wiki's own pages rather than in an
    # external document (Issue #675).
    RootOutput(".wikicommit/view", ALL, origin="init"),
    RootOutput(".wikicommit/source", ALL, origin="init"),
    # Quality gate configs: every variant, because wikicommit-merge depends on them
    # regardless of the Quartz choice.
    RootOutput(".lychee.toml", ALL, origin="init", template=".lychee.toml"),
    RootOutput(".markdownlint.json", ALL, origin="init", template=".markdownlint.json"),
    # pageTitle / footer URL substitution, not a copy (Issue #317 / #557).
    RootOutput("quartz.config.yaml", QUARTZ, origin="init"),
    RootOutput("package.json", QUARTZ, origin="init", template="package.json"),
    RootOutput("prebuild-symlinks.cjs", QUARTZ, origin="init", template="prebuild-symlinks.cjs"),
    RootOutput("repair-plugin-builds.cjs", QUARTZ, origin="init", template="repair-plugin-builds.cjs"),
    RootOutput("install-local-plugins.cjs", QUARTZ, origin="init", template="install-local-plugins.cjs"),
    # deploy.yml is the one piece that opts the repository into automatic GitHub Pages
    # publishing on every merge to main, so it is gated behind --quartz-pages alone
    # (Issue #335); --quartz by itself only sets up local build/preview.
    RootOutput(
        ".github/workflows/deploy.yml",
        PAGES_ONLY,
        origin="init",
        template="workflows/deploy.yml",
    ),
    # Unlike deploy.yml above, this workflow backs the review pipeline (wikicommit-merge
    # → tracking Issue → Issue close), which does not depend on the Quartz publishing
    # choice (Issue #313).
    RootOutput(
        ".github/workflows/review-issue-close-sync.yml",
        ALL,
        origin="init",
        template="workflows/review-issue-close-sync.yml",
    ),
    # wikicommit-banner's "report an issue" link (Issue #245/#313) points at
    # ?template=report.md, which silently no-ops without this file. Quartz-only because
    # wikicommit-banner is itself a Quartz plugin (Issue #339).
    RootOutput(
        ".github/ISSUE_TEMPLATE/report.md",
        QUARTZ,
        origin="init",
        template=".github/ISSUE_TEMPLATE/report.md",
    ),
    # Directory tree, with dev-only files excluded.
    RootOutput("quartz-plugins", QUARTZ, origin="init"),
    RootOutput(".gitmodules", QUARTZ, origin="submodule"),
    RootOutput("quartz", QUARTZ, origin="submodule"),
    RootOutput(".wikicommit/schemaorg-vocab.json", ALL, origin="init", condition="vocab_cache"),
    RootOutput("package-lock.json", QUARTZ, origin="npm", in_git_add=False),
)


def _validate() -> None:
    """Reject a mistyped `origin`/`condition`/variant at import time.

    Every one of these fields decides whether an entry reaches init.py's copies or the
    printed `git add`, and an unrecognized value fails open on both sides: an unknown
    origin is simply "not init" (never copied) and an unknown condition is "not always"
    (listed only when the vocabulary cache happened to be created). Both read as a
    deliberate exclusion, which is precisely the silent drift this list replaces.
    """
    seen: set[str] = set()
    for entry in ROOT_OUTPUTS:
        if entry.path in seen:
            raise ValueError(f"duplicate root output: {entry.path!r}")
        seen.add(entry.path)
        unknown = entry.variants - ALL
        if unknown or not entry.variants:
            raise ValueError(f"{entry.path}: unknown or empty variants: {unknown or entry.variants}")
        if entry.origin not in ORIGINS:
            raise ValueError(f"{entry.path}: unknown origin: {entry.origin!r}")
        if entry.condition not in CONDITIONS:
            raise ValueError(f"{entry.path}: unknown condition: {entry.condition!r}")
        if entry.template is not None and entry.origin != "init":
            raise ValueError(f"{entry.path}: origin={entry.origin!r} cannot carry a template")


_validate()


def for_variant(variant: str) -> tuple[RootOutput, ...]:
    """Every entry that applies to `variant`, in `git add` order."""
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant: {variant!r}")
    return tuple(entry for entry in ROOT_OUTPUTS if variant in entry.variants)


def _condition_holds(condition: str, *, vocab_cache_created: bool) -> bool:
    """Whether a conditional path exists for this run.

    Spelled out per value rather than as "not always means the vocab cache flag": a new
    CONDITIONS member added without a branch here has to fail loudly instead of quietly
    keying off an unrelated flag.
    """
    if condition == "always":
        return True
    if condition == "vocab_cache":
        return vocab_cache_created
    raise ValueError(f"unknown condition: {condition!r}")


def git_add_paths(variant: str, *, vocab_cache_created: bool = False) -> list[str]:
    """The paths the printed `git add` command should list, in order."""
    return [
        entry.path
        for entry in for_variant(variant)
        if entry.in_git_add
        and _condition_holds(entry.condition, vocab_cache_created=vocab_cache_created)
    ]


def plain_copies(variant: str) -> list[tuple[str, str]]:
    """`(template-relative source, repository-relative destination)` pairs that
    init.py can copy verbatim, in declaration order."""
    return [
        (entry.template, entry.path)
        for entry in for_variant(variant)
        if entry.origin == "init" and entry.template is not None
    ]
