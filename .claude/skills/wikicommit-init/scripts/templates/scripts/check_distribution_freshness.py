#!/usr/bin/env python3
"""check_distribution_freshness.py — is the installed distribution still current?

Named for the `check_ingest_freshness.py` / `check_derivation_freshness.py` family,
which all ask the same question: is what was recorded still true? Unlike
`check_ingest_freshness.py`, this one has no side effects — it never writes.

A wiki repository holds three kinds of thing (Issue #712), and only the first is the
user's to keep:

  - content and configuration the user authors (`entity/`, `config.yml`, `schema/`)
  - WikiCommit's own payload, which the user never edits (`.wikicommit/scripts/`,
    `quartz-plugins/`, the two workflows, the `*.cjs` build scripts)
  - things generated elsewhere (`quartz/`, `package-lock.json`)

Until Issue #712 the second kind was treated like the first, so a repository initialized
a version ago silently kept running the old workflow, the old plugin `dist/` and the old
build scripts, and the only way to find out was to clone it and diff by hand. This script
makes that visible; `/wikicommit-init` refreshes it.

Which policy each path gets is declared once, in `_root_outputs.py` — the same list that
drives init.py's copies and print_next_steps.py's `git add` guidance. Keeping a second
copy of the classification here is exactly the drift that list exists to remove.

Usage:
    python .wikicommit/scripts/check_distribution_freshness.py
        [--variant <variant>] [--repo-root <path>] [--only <root output path>]

Exit code: always 0 (report only, like the rest of /wikicommit-status).
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import yaml

TEMPLATES_REL = Path(".claude/skills/wikicommit-init/scripts")

# Never walked on either side: npm's install tree and Python's bytecode cache are not
# distribution content, and copy_tree() prunes both for the same reason.
_PRUNED_DIRS = {"node_modules", "__pycache__"}

# The update policies this script knows how to act on; see check() for why.
_HANDLED_POLICIES = frozenset(("overwrite", "review", "skip"))

# Appended to `.wikicommit/scripts` alone (Issue #930). A stale copy there means the
# instructions a Skill is executing right now were written against newer scripts, and the
# mismatch does not always announce itself: when only the inside of an existing option
# changed, the old script can fail in a way that names the wrong cause. For quartz-plugins
# or the workflows a stale copy means a stale published site or CI job instead, so a
# suffix shared by every OUTDATED line would be wrong on most of them.
#
# It states the consequence and stops there (Issue #935). It used to end with
# "Run /wikicommit-update.", which is wrong at one of the six places that run this check
# and redundant at two more: three of them belong to /wikicommit-update itself, and the
# one in its last step runs *after* the update, so a line there reports that the update
# just made did not take — prescribing the command that has only now failed. The
# consequence holds at every call site; what to do about it is what each SKILL.md already
# says in context, which is why this string carries the first and not the second.
_SCRIPTS_CONSEQUENCE = (
    ". The installed Skills were refreshed and these scripts were not, so an instruction "
    "written against the new scripts can meet an older one here and fail in a way that "
    "names the wrong cause."
)


def _consequence(path: str) -> str:
    return _SCRIPTS_CONSEQUENCE if path == ".wikicommit/scripts" else ""


def _load_root_outputs(repo_root: Path):
    """Import `_root_outputs` from the installed wikicommit-init Skill, or None.

    The Skill tree is not guaranteed to be present: `.wikicommit/scripts/` is committed
    to the wiki repository, while `.claude/skills/` is installed separately and may have
    been removed or never added. Without it there is no template to compare against, so
    the honest answer is to say so and report nothing — the same non-blocking degradation
    `check_property_wikilink_reinforcement.py` takes when the Schema.org vocabulary
    cannot be read.
    """
    module_path = repo_root / TEMPLATES_REL / "_root_outputs.py"
    if not module_path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("_root_outputs_installed", module_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except Exception:
        return None
    finally:
        sys.dont_write_bytecode = previous
    return module


def detect_variant(repo_root: Path) -> str:
    """Which `/wikicommit-init` variant this repository looks like.

    Read off the two files that variant actually gates rather than off any recorded
    setting, because nothing records it: `quartz.config.yaml` is what `--quartz` adds,
    and `deploy.yml` is the single thing `--quartz-pages` adds on top (Issue #335).
    """
    if not (repo_root / "quartz.config.yaml").is_file():
        return "none"
    if (repo_root / ".github" / "workflows" / "deploy.yml").is_file():
        return "quartz_pages"
    return "quartz_only"


def _installed_version(repo_root: Path) -> str:
    """The version the *template tree* ships, or "unknown"."""
    version_file = repo_root / TEMPLATES_REL / "templates" / "scripts" / "_version.py"
    if not version_file.is_file():
        return "unknown"
    for line in version_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("VERSION"):
            _, _, value = line.partition("=")
            return value.strip().strip("\"'") or "unknown"
    return "unknown"


def _synced_version(repo_root: Path) -> str:
    """`wikicommit_version` from config.yml, or "unknown".

    Absent means the repository predates Issue #577, which stamped it. No date-based
    guess is made: every comparison below runs on the files themselves regardless, so
    the version is reported for the reader's benefit and never gates a check.
    """
    config = repo_root / ".wikicommit" / "config.yml"
    if not config.is_file():
        return "unknown"
    try:
        data = yaml.safe_load(config.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return "unknown"
    if not isinstance(data, dict):
        return "unknown"
    version = data.get("wikicommit_version")
    return str(version) if version else "unknown"


def _key_paths(value, prefix: str = "") -> set[str]:
    """Every mapping key in `value`, as dotted paths.

    Recursive rather than top-level-only because the keys that actually get added
    upstream are nested: `quartz.config.yaml` has three top-level keys and never gains a
    fourth, while `pageTitleSuffix` (Issue #679) arrived under `configuration`. Lists are
    not descended into — their contents are the user's values, not schema.
    """
    if not isinstance(value, dict):
        return set()
    paths: set[str] = set()
    for key, child in value.items():
        path = f"{prefix}{key}"
        paths.add(path)
        paths |= _key_paths(child, prefix=f"{path}.")
    return paths


# `{NAME}` placeholders init.py substitutes at write time. YAML reads an unquoted one as
# a flow mapping, so `theme: {THEME}` parses as a *nested key* named THEME — which the
# initialized file, holding a real value, never has. Left alone, every freshly created
# repository reports its own config.yml and quartz.config.yaml as OUTDATED forever: the
# permanently-lit warning this comparison mode exists to avoid. `options: {}` and other
# genuine empty mappings do not match, so they keep parsing as themselves.
#
# The substitute has to be a *bare scalar*, not `""`. A placeholder is not always written
# bare: config.yml's first line is `wikicommit_version: "{VERSION}"`, already inside
# quotes, and substituting `""` there produced `""""` — invalid YAML, which
# `yaml.safe_load` rejected for the whole document. The template's key set then came back
# empty, so `template - local` was empty too and **config.yml could never report a key
# added upstream**: the comparison was switched off while still looking like it ran. A
# bare token is valid in both positions and stays a plain scalar either way.
_PLACEHOLDER_RE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")
_PLACEHOLDER_VALUE = "WIKICOMMIT_PLACEHOLDER"


def _yaml_keys(path: Path, *, is_template: bool = False) -> set[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    if is_template:
        text = _PLACEHOLDER_RE.sub(_PLACEHOLDER_VALUE, text)
    try:
        return _key_paths(yaml.safe_load(text))
    except yaml.YAMLError as exc:
        # An unparseable *template* is WikiCommit's own bug, and its only symptom is an
        # empty key set — which reads exactly like "nothing was added upstream". Say so
        # rather than reporting a clean result the comparison never actually computed.
        if is_template:
            print(
                f"WARNING: {path} could not be parsed as YAML ({exc.__class__.__name__}), "
                "so no key comparison was made against it."
            )
        return set()


def _frontmatter_keys(path: Path) -> set[str]:
    """Keys under `wikicommit:` in a policy file's frontmatter.

    Only the frontmatter is read. The body is the user's own prose — the shipped template
    is a commented-out example that tells the reader to replace it — so any repository
    actually using the file differs there by design.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    if not text.startswith("---"):
        return set()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return set()
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return set()
    if not isinstance(data, dict):
        return set()
    return _key_paths(data.get("wikicommit"))


def _json_keys(path: Path) -> set[str]:
    """Key paths in a JSON object — for `.claude/settings.json` (Issue #953).

    Additive like the two above, and for the same reason: init merges three
    `skillOverrides` entries into a file whose other contents (permissions, env, hooks)
    are entirely the user's, and whose values for those three they may have deliberately
    changed. A byte comparison would report every initialized repository as OUTDATED
    forever. What is worth knowing is only whether the template names a Skill this file
    has no entry for at all.

    Keys, never values. `"wikicommit-generate": "on"` is the user running unattended on
    purpose, and reporting it as drift would push them toward undoing it.

    An unreadable or non-object file yields an empty set. On the local side that reads as
    "has no keys", so every template key is reported as missing — which is true, and init
    prints its own warning about the same file.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, dict):
        return set()
    return _key_paths(data)


def _meaningful_lines(path: Path) -> set[str]:
    """Non-blank, non-comment lines — for files the local copy appends to.

    `.gitignore` is the case: init copies the template and then appends a Quartz section,
    so a `--quartz` repository can never byte-match. What is still worth knowing is
    whether a pattern the template added upstream is missing here, which is a containment
    test rather than an equality one.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set()
    return {
        stripped
        for line in lines
        if (stripped := line.strip()) and not stripped.startswith("#")
    }


def _walk(root: Path, exclude=None) -> dict[str, Path]:
    """Every file under `root`, keyed by its path relative to `root`."""
    found: dict[str, Path] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNED_DIRS]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(root)
            if exclude is not None and exclude(rel):
                continue
            found[rel.as_posix()] = file_path
    return found


def _same_bytes(a: Path, b: Path) -> bool:
    try:
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def check(repo_root: Path, variant: str | None, only: str | None = None) -> int:
    root_outputs = _load_root_outputs(repo_root)
    templates_dir = repo_root / TEMPLATES_REL / "templates"
    module_path = repo_root / TEMPLATES_REL / "_root_outputs.py"
    if root_outputs is None or not templates_dir.is_dir():
        # Two different situations reach here and they call for opposite responses, so
        # they must not share a message: the Skill really is absent (install it), or it
        # is present but its list would not load (a broken entry upstream, which
        # "install the Skills" would send the reader chasing the wrong thing).
        if module_path.is_file() and templates_dir.is_dir():
            print(
                f"WARNING: {module_path} is present but could not be loaded, so there is "
                "no classification to compare against. Re-run it directly to see the error."
            )
        else:
            print(
                "WARNING: wikicommit-init is not installed in this repository "
                f"({TEMPLATES_REL}/templates/ not found), so there is no template to compare "
                "against. Install the Skills to enable this check.",
            )
        print("SUMMARY: outdated=0, missing=0, orphan=0")
        return 0

    variant = variant or detect_variant(repo_root)
    entries = list(root_outputs.for_variant(variant))
    if only is not None:
        # A typo would otherwise compare nothing and report a clean result — the same
        # shape of silent wrong answer this flag exists to catch, so it has to be said.
        # Naming a real entry this script never looks at (`update: skip`, or one that
        # ships no template) produces the identical clean summary, so it gets the same
        # treatment: the point is that a quiet run has to mean "compared and in step".
        if not any(e.path == only for e in entries):
            print(f"WARNING: --only {only} names no root output in this variant.")
        entries = [e for e in entries if e.path == only]
    else:
        # Suppressed under --only: `synced` is config.yml's wikicommit_version, which only
        # /wikicommit-update writes, so it stays behind on a repository that re-ran init and
        # is genuinely in step. Harmless in a full report beside the byte comparison; in a
        # one-line narrowed check it would be the loudest thing printed and it would be wrong.
        print(f"VERSION: synced={_synced_version(repo_root)}, installed={_installed_version(repo_root)}")

    outdated = missing = orphan = compared = 0

    for entry in entries:
        # Normalized against the policies *this script* has a branch for, not just the
        # ones the imported list recognizes. `npx skills add` refreshes .claude/skills/
        # while .wikicommit/scripts/ only catches up on the next init, so this script can
        # be older than the list it reads and meet a policy added upstream. Behaviorally
        # it would already fall through to the review path; normalizing here keeps the
        # label from announcing a treatment that is not the one being applied.
        policy = root_outputs.update_policy(entry)
        if policy not in _HANDLED_POLICIES:
            policy = "review"
        if policy == "skip":
            continue
        template_rel = root_outputs.template_source(entry)
        if template_rel is None:
            continue
        template_path = templates_dir / template_rel
        local_path = repo_root / entry.path
        if not template_path.exists():
            continue
        compared += 1

        if template_path.is_dir():
            # quartz-plugins ships vitest/eslint config and *.test.ts that init
            # deliberately does not copy; without the same exclusion every one of them
            # would be reported MISSING on every run.
            exclude = (
                root_outputs.is_quartz_plugin_dev_artifact
                if entry.path == "quartz-plugins"
                else None
            )
            template_files = _walk(template_path, exclude=exclude)
            if not local_path.is_dir():
                print(f"MISSING: {entry.path} ({policy}) — not present locally")
                missing += 1
                continue
            local_files = _walk(local_path, exclude=exclude)
            differing = sum(
                1
                for rel, src in template_files.items()
                if rel not in local_files or not _same_bytes(src, local_files[rel])
            )
            if differing:
                print(
                    f"OUTDATED: {entry.path} ({policy}) — "
                    f"{differing} file(s) differ from the template{_consequence(entry.path)}"
                )
                outdated += 1
            # Orphans are only meaningful where the whole tree is WikiCommit's: a file
            # under `.wikicommit/schema/` that the template lacks is the user's own type
            # (a custom type, or one Pass 2b added), not a leftover.
            if policy == "overwrite":
                for rel in sorted(set(local_files) - set(template_files)):
                    print(
                        f"ORPHAN: {entry.path}/{rel} — no counterpart in the template"
                    )
                    orphan += 1
            continue

        if not local_path.exists():
            print(f"MISSING: {entry.path} ({policy}) — not present locally")
            missing += 1
            continue

        if entry.compare == "bytes":
            if not _same_bytes(template_path, local_path):
                print(f"OUTDATED: {entry.path} ({policy}) — differs from the template")
                outdated += 1
            continue

        # Additive-only comparisons. What the user changed is theirs; what the template
        # gained since they initialized is the thing worth surfacing.
        if entry.compare == "yaml_keys":
            gained = _yaml_keys(template_path, is_template=True) - _yaml_keys(local_path)
            label = "key(s)"
        elif entry.compare == "frontmatter_keys":
            gained = _frontmatter_keys(template_path) - _frontmatter_keys(local_path)
            label = "wikicommit: key(s)"
        elif entry.compare == "json_keys":
            gained = _json_keys(template_path) - _json_keys(local_path)
            label = "JSON key(s)"
        elif entry.compare == "lines":
            gained = _meaningful_lines(template_path) - _meaningful_lines(local_path)
            label = "line(s)"
        else:
            continue

        if gained:
            listed = ", ".join(sorted(gained))
            print(
                f"OUTDATED: {entry.path} ({policy}) — "
                f"the template has {label} this file lacks: {listed}"
            )
            outdated += 1

    if only is not None and entries and not compared:
        # Reached only when --only named a real entry that has no comparison behind it,
        # so the counts below were never computed for it. Saying nothing here would let
        # `SUMMARY: outdated=0` stand in for "in step", which it does not.
        print(
            f"WARNING: --only {only} names a root output this script does not compare "
            "(its update policy is `skip`, or it ships no template), so the summary "
            "below says nothing about whether it is in step."
        )

    print(f"SUMMARY: outdated={outdated}, missing={missing}, orphan={orphan}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        choices=("none", "quartz_only", "quartz_pages"),
        default=None,
        help="Override the auto-detected /wikicommit-init variant",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        metavar="PATH",
        help="Repository root (default: the current directory)",
    )
    parser.add_argument(
        "--only",
        metavar="PATH",
        default=None,
        help="Compare this one root output only (e.g. .wikicommit/scripts)",
    )
    args = parser.parse_args()
    return check(Path(args.repo_root).resolve(), args.variant, args.only)


if __name__ == "__main__":
    sys.exit(main())
