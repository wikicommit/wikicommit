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

import re
from dataclasses import dataclass
from pathlib import Path

VARIANTS = ("none", "quartz_only", "quartz_pages")

# Who puts the path there. Free strings would let a typo (`"Init"`) silently drop an entry
# from plain_copies() while git_add_paths() keeps listing it — the drift this module exists
# to remove — so the accepted values are enumerated and checked.
ORIGINS = ("init", "install", "submodule", "npm")

# When the path exists. Each value needs its own answer in git_add_paths(); a new one must be
# wired up there rather than silently falling through to whatever the last branch tests.
CONDITIONS = ("always", "vocab_cache")

# How an update should treat the path (Issue #712). This is an ownership question, not a
# question about file type: `overwrite` is WikiCommit's own payload, which a re-init
# refreshes because the user never authors it; `review` may carry the user's own edits, so
# init never touches it and an update flow shows a diff instead; `skip` is not ours to
# compare at all (the user's content, an origin other than init, or a regenerable cache).
#
# `review` and `skip` behave identically during init — both protect what is already there.
# What they separate is whether a drift report has anything to say about the path.
UPDATE_POLICIES = ("overwrite", "review", "skip")

# The policy a value that this module does not recognize is treated as. A wiki repository
# can end up with an old `.wikicommit/scripts/` reading a NEW `_root_outputs.py` (npx skills
# add refreshes the Skill tree; the scripts tree only catches up on the next init), so a
# policy added upstream will be read by a checker that has never heard of it. Falling back
# to the conservative end keeps that combination from either crashing or, worse, deciding
# an unknown policy means "overwrite the user's file".
UNKNOWN_UPDATE_POLICY = "review"

# How the freshness check decides a path has drifted. Byte equality is the default and the
# right answer for anything WikiCommit writes and the user does not edit. It is the wrong
# answer for the four paths whose template carries placeholders or a "delete this and write
# your own" comment, and for .gitignore, which init appends a Quartz section to: those can
# never byte-match a real repository, so byte comparison would light permanently. A warning
# that is always on stops being read — the failure this repository has already had to undo
# once, when Issue #562 demoted the low-density guard for exactly that reason — and a drift
# report nobody reads defeats the point of having one.
#
# So those paths report only *additive* signals: something the template has that the local
# copy lacks. Changing a value or rewriting the prose is the user doing their job, and is
# never reported.
COMPARISONS = (
    "bytes",            # byte-for-byte, file or directory tree
    "yaml_keys",        # top-level YAML keys the template has and the local file lacks
    "frontmatter_keys", # keys under `wikicommit:` in frontmatter, same additive test
    "lines",            # template lines (ignoring blanks/comments) absent from the local file
    "none",             # not compared; the only valid choice for update="skip"
)

_TEST_ARTIFACT_RE = re.compile(r"\.test\.tsx?$")


def is_quartz_plugin_dev_artifact(rel_path: Path) -> bool:
    """vitest suites/config (#93) and eslint config (#94) are dev-only tooling
    for the template's own CI and are not needed by the generated site
    (dist/ is pre-built).

    It lives here rather than in init.py because both sides of the same fact need it
    (Issue #712): init.py excludes these from the copy, and the freshness check has to
    make the same exclusion or it reports every one of them as MISSING on every run.
    Two copies of the rule would drift, and the drift would surface as permanent noise
    in exactly the report this list exists to make trustworthy.
    """
    return (
        rel_path.name in ("vitest.config.ts", "eslint.config.js")
        or _TEST_ARTIFACT_RE.search(rel_path.name) is not None
    )

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

    update: str = "review"
    """One of UPDATE_POLICIES. Defaults to the protective end: an entry added without an
    explicit decision is never overwritten, mirroring init.py's existing rule that
    always_skip_existing wins if both flags are ever passed."""

    compare: str = "bytes"
    """One of COMPARISONS. Must be `none` exactly when `update` is `skip`."""

    compare_template: str | None = None
    """Path under `templates/` the freshness check compares against, for entries init.py
    cannot copy verbatim — a directory tree, or a file whose placeholders are substituted
    at init time. Entries carrying `template` are compared against that instead; the two
    are never both set. `None` on an entry that is not `skip` means nothing under
    `templates/` corresponds to it."""


# Order is the order the `git add` line lists them in.
ROOT_OUTPUTS: tuple[RootOutput, ...] = (
    RootOutput(".claude", ALL, origin="install", update="skip", compare="none"),
    RootOutput(".gitignore", ALL, origin="init", template=".gitignore", compare="lines"),
    # Placeholder substitution (version/targets/primary_lang/theme), not a copy.
    RootOutput(
        ".wikicommit/config.yml",
        ALL,
        origin="init",
        compare="yaml_keys",
        compare_template="config.yml",
    ),
    # Written by hand after init, and the Skills only ever append to its `rejected:`
    # list, so a re-run must never overwrite it (init.py copies every entry here with
    # always_skip_existing=True, the same protection .lychee.toml gets).
    RootOutput(
        ".wikicommit/source-policy.md",
        ALL,
        origin="init",
        template="source-policy.md",
        compare="frontmatter_keys",
    ),
    # Same shape and the same protection as source-policy.md, one axis over: that file
    # says which sources come in, this one says whether an entity may be written about
    # at all (Issue #667). Hand-edited prose, so a re-run must never overwrite it.
    RootOutput(
        ".wikicommit/entity-policy.md",
        ALL,
        origin="init",
        template="entity-policy.md",
        compare="frontmatter_keys",
    ),
    # The review discipline, in one place (Issue #752). `overwrite` is deliberate and is
    # the opposite of the two policy files above: those hold the user's own prose, this
    # holds WikiCommit's rules, and letting a repository edit it would let a wiki quietly
    # weaken its own review. check_distribution_freshness.py compares it byte for byte, so
    # an upstream change reaches every repository on its next init.
    RootOutput(
        ".wikicommit/review-rules.md",
        ALL,
        origin="init",
        template="review-rules.md",
        update="overwrite",
    ),
    # Directory trees and created-with-.gitkeep directories.
    RootOutput(".wikicommit/schema", ALL, origin="init", compare_template="schema"),
    RootOutput(
        ".wikicommit/scripts",
        ALL,
        origin="init",
        update="overwrite",
        compare_template="scripts",
    ),
    RootOutput(".wikicommit/entity", ALL, origin="init", update="skip", compare="none"),
    # Second-order pages, grounded in this wiki's own pages rather than in an
    # external document (Issue #675).
    RootOutput(".wikicommit/view", ALL, origin="init", update="skip", compare="none"),
    RootOutput(".wikicommit/source", ALL, origin="init", update="skip", compare="none"),
    # Immutable per-review records (Issue #750). `skip` for the same reason as the three
    # trees above: this is the wiki's own accumulated history, not a distribution payload,
    # so an update has nothing here to refresh and nothing to compare against. It is listed
    # rather than left out because the first commit has to contain it — the records are the
    # evidence that a review happened at all, and a run whose records were never committed
    # is indistinguishable from one that never reviewed anything.
    RootOutput(".wikicommit/review", ALL, origin="init", update="skip", compare="none"),
    # Quality gate configs: every variant, because wikicommit-merge depends on them
    # regardless of the Quartz choice.
    RootOutput(".lychee.toml", ALL, origin="init", template=".lychee.toml"),
    RootOutput(".markdownlint.json", ALL, origin="init", template=".markdownlint.json"),
    # pageTitle / footer URL substitution, not a copy (Issue #317 / #557).
    RootOutput(
        "quartz.config.yaml",
        QUARTZ,
        origin="init",
        compare="yaml_keys",
        compare_template="quartz.config.yaml",
    ),
    RootOutput("package.json", QUARTZ, origin="init", template="package.json"),
    RootOutput(
        "prebuild-symlinks.cjs",
        QUARTZ,
        origin="init",
        template="prebuild-symlinks.cjs",
        update="overwrite",
    ),
    RootOutput(
        "repair-plugin-builds.cjs",
        QUARTZ,
        origin="init",
        template="repair-plugin-builds.cjs",
        update="overwrite",
    ),
    RootOutput(
        "install-local-plugins.cjs",
        QUARTZ,
        origin="init",
        template="install-local-plugins.cjs",
        update="overwrite",
    ),
    # deploy.yml is the one piece that opts the repository into automatic GitHub Pages
    # publishing on every merge to main, so it is gated behind --quartz-pages alone
    # (Issue #335); --quartz by itself only sets up local build/preview.
    RootOutput(
        ".github/workflows/deploy.yml",
        PAGES_ONLY,
        origin="init",
        template="workflows/deploy.yml",
        update="overwrite",
    ),
    # Unlike deploy.yml above, this workflow backs the review pipeline (wikicommit-merge
    # → tracking Issue → Issue close), which does not depend on the Quartz publishing
    # choice (Issue #313).
    RootOutput(
        ".github/workflows/review-issue-close-sync.yml",
        ALL,
        origin="init",
        template="workflows/review-issue-close-sync.yml",
        update="overwrite",
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
    RootOutput(
        "quartz-plugins",
        QUARTZ,
        origin="init",
        update="overwrite",
        compare_template="quartz-plugins",
    ),
    RootOutput(".gitmodules", QUARTZ, origin="submodule", update="skip", compare="none"),
    RootOutput("quartz", QUARTZ, origin="submodule", update="skip", compare="none"),
    RootOutput(
        ".wikicommit/schemaorg-vocab.json",
        ALL,
        origin="init",
        condition="vocab_cache",
        update="skip",
        compare="none",
    ),
    RootOutput(
        "package-lock.json",
        QUARTZ,
        origin="npm",
        in_git_add=False,
        update="skip",
        compare="none",
    ),
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
        if entry.update not in UPDATE_POLICIES:
            raise ValueError(f"{entry.path}: unknown update policy: {entry.update!r}")
        if entry.compare not in COMPARISONS:
            raise ValueError(f"{entry.path}: unknown comparison: {entry.compare!r}")
        # Tied together deliberately: "not ours to compare" and "here is how to compare it"
        # are the same decision stated twice, and letting them disagree would leave an
        # entry that is either silently never checked or checked against nothing.
        if (entry.update == "skip") != (entry.compare == "none"):
            raise ValueError(
                f"{entry.path}: update={entry.update!r} and compare={entry.compare!r} disagree "
                "— skip requires compare='none', and every other policy requires a real one"
            )
        if entry.template is not None and entry.compare_template is not None:
            raise ValueError(
                f"{entry.path}: carries both template and compare_template; "
                "compare_template is only for entries init.py cannot copy verbatim"
            )


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


def update_policy(entry: "RootOutput") -> str:
    """`entry.update`, or UNKNOWN_UPDATE_POLICY when this module does not recognize it.

    Reading it through here rather than off the field is what keeps an old checker
    working against a newer list (see UNKNOWN_UPDATE_POLICY). `_validate()` rejects an
    unknown value written *in this file*, so the fallback only ever fires for a value a
    future version introduced.
    """
    return entry.update if entry.update in UPDATE_POLICIES else UNKNOWN_UPDATE_POLICY


def copy_flags(entry: "RootOutput") -> dict:
    """The `copy_file()` / `copy_tree()` / `write_file()` keyword flags this entry's
    update policy implies.

    `overwrite` refreshes WikiCommit's own payload even under --no-overwrite; everything
    else protects what is already on disk. init.py derives its flags from here so the
    ownership decision lives in one place instead of being restated at each call site
    (Issue #712) — the same reason plain_copies() exists.
    """
    if update_policy(entry) == "overwrite":
        return {"always_overwrite": True}
    return {"always_skip_existing": True}


def by_path(path: str) -> "RootOutput | None":
    """The entry declaring `path`, or None."""
    for entry in ROOT_OUTPUTS:
        if entry.path == path:
            return entry
    return None


def template_source(entry: "RootOutput") -> str | None:
    """The `templates/`-relative path this entry is compared against, if any."""
    return entry.template if entry.template is not None else entry.compare_template


def plain_copies(variant: str) -> list[tuple[str, str]]:
    """`(template-relative source, repository-relative destination)` pairs that
    init.py can copy verbatim, in declaration order."""
    return [
        (entry.template, entry.path)
        for entry in for_variant(variant)
        if entry.origin == "init" and entry.template is not None
    ]
