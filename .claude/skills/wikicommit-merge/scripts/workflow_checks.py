#!/usr/bin/env python3
"""workflow_checks.py — the wikicommit-merge knowledge `skill_workflow.py` does not have.

`skill_workflow.py` walks `workflow.yaml` and knows nothing about this Skill. Which paths a
merge carries, what a merge branch is called, and what "the PR was merged" looks
like live here, next to the workflow, so the engine stays the same one
`wikicommit-generate` uses.

Every subcommand runs from the repository root and follows the same contract as
generate's checks:

- **exit 0** means yes (a condition holds, a check passed, a list was produced)
- **exit 1** means no, with the reason on stdout
- `ITEM: <value>` lines are a produced list; any other line is shown to the user

None of these checks print `TOUCHED:`. A merge's own run never holds files for
`skill_workflow.py check-merge` to protect: the files it handles are the change itself.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Run directly (as `references/*.md` tell the agent to) rather than through the engine,
# nothing passes PYTHONIOENCODING=utf-8: on a cp1252 terminal or pipe an `ITEM:` holding
# a Japanese path raised UnicodeEncodeError at `print`. So the streams are set to UTF-8
# here, before the import below can print, and not in the shared module, which an older
# `.wikicommit/scripts/` does not have. The same streams and error handlers as
# skill_workflow.use_utf8_streams(); only when run, not when a test imports the module.
if __name__ == "__main__":
    for _stream, _errors in ((sys.stdin, "replace"), (sys.stdout, "strict"),
                             (sys.stderr, "backslashreplace")):
        try:
            _stream.reconfigure(encoding="utf-8", errors=_errors)
        except (AttributeError, ValueError, OSError):
            pass

# The helpers every Skill's checks read the same way live in
# `.wikicommit/scripts/_workflow_checks.py` (Issue #1219). A wiki whose scripts predate
# it has none until `/wikicommit-update` is merged; the same goes for
# `check_external_links.py`, whose batching `links` shares with `/wikicommit-status`.
# Exit 2, not 1, whatever is missing: a `when:` condition exiting 1 would read as
# "skip this step", while 2 stops the engine. Only a module of `.wikicommit/scripts/`
# is fixed by `/wikicommit-update`; a missing PyYAML is not, so it gets its own
# pointer. This bootstrap cannot live in the module it loads, so each Skill carries it;
# tests/test_workflow_checks_shared.py holds the four copies to one shape.
sys.path.insert(0, str(Path.cwd() / ".wikicommit" / "scripts"))
try:
    from _workflow_checks import listed, norm, parse_porcelain_z, read_markdown, read_run, run
    from _frontmatter import parse_frontmatter_text
    from check_external_links import check_link_batches
except ImportError as e:
    if isinstance(e, ModuleNotFoundError) and e.name == "yaml":
        print(f"PyYAML is not installed ({e}); install it (pip install pyyaml) and run again")
    else:
        print(".wikicommit/scripts/ is missing a module this Skill needs or is older than "
              f"this Skill ({e}); run /wikicommit-update first")
    sys.exit(2)

# Everything this Skill carries. The commit step stages these, so after a commit
# none of them may still show as changed.
PATHSPECS = (
    ".wikicommit/entity/**/*.md",
    ".wikicommit/view/**/*.md",
    ".wikicommit/source/**/*.md",
    ".wikicommit/review/**/*.md",
    ".wikicommit/entity/assets/**",
    ".wikicommit/source-policy.md",
    ".wikicommit/entity-policy.md",
    ".wikicommit/relations.yml",
)

BRANCH_PREFIX = "wikicommit/merge-"
FALLBACK_BRANCH = "main"


def read_state(run: str) -> dict:
    return read_run(run)[1]


def porcelain(pathspecs, ignored: bool = False) -> list[tuple[str, str]] | None:
    """`(status code, path)` per changed path, or None when `git status` fails.

    `-z`: without it, git still wraps a path holding a space, a quote or a
    backslash in double quotes (core.quotePath only covers non-ASCII), and the
    list would carry a path that does not exist. `--untracked-files=all`: a new
    directory would otherwise show as the directory, not the files in it.
    """
    argv = ["git", "status", "--porcelain", "-z", "--untracked-files=all"]
    if ignored:
        argv.append("--ignored")
    result = run([*argv, "--", *pathspecs])
    if result.returncode != 0:
        return None
    return parse_porcelain_z(result.stdout)


def changed_paths() -> list[str] | None:
    found = porcelain(PATHSPECS)
    return None if found is None else [path for _, path in found]


def current_branch() -> str:
    result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return result.stdout.strip() if result.returncode == 0 else ""


def default_branch(state: dict) -> str:
    values = listed(state, "default_branch")
    return values[0] if values else FALLBACK_BRANCH


# --- script steps -------------------------------------------------------------


def cmd_freshness(args) -> int:
    """Warn when `.wikicommit/scripts/` is out of step with this Skill. Never stops.

    Runs the copy in the Skill tree: the one under `.wikicommit/scripts/` is the
    half that may be stale. No Skill tree copy means nothing to compare against.
    """
    here = Path(__file__).resolve().parent
    checker = (here.parent.parent / "wikicommit-init" / "scripts" / "templates"
               / "scripts" / "check_distribution_freshness.py")
    if not checker.is_file():
        return 0
    result = run([sys.executable, str(checker), "--only", ".wikicommit/scripts"])
    for line in result.stdout.splitlines():
        if line.startswith(("OUTDATED:", "MISSING:", "ORPHAN:", "WARNING:")):
            print(line)
    return 0


def cmd_default_branch(args) -> int:
    """The repository's default branch, or `main` with a warning. Never stops."""
    result = run(["gh", "repo", "view", "--json", "defaultBranchRef",
                  "-q", ".defaultBranchRef.name"])
    name = result.stdout.strip() if result.returncode == 0 else ""
    if not name:
        name = FALLBACK_BRANCH
        print(f"WARNING: the default branch could not be read from GitHub; using "
              f"{FALLBACK_BRANCH!r}. Opening the PR and returning to the default branch "
              "will fail if the repository's real default branch differs.")
    print(f"DEFAULT_BRANCH: {name}")
    print(f"ITEM: {name}")
    return 0


def cmd_detect(args) -> int:
    """The changes this Skill would carry, one `ITEM:` per path."""
    paths = changed_paths()
    if paths is None:
        print("git status failed; is this a Git repository?")
        return 1
    for path in paths:
        print(f"ITEM: {path}")
    return 0


def cmd_open_runs(args) -> int:
    """Refuse the work of another run that has not finished."""
    engine = Path(".wikicommit/scripts/skill_workflow.py")
    if not engine.is_file():
        print("NOTE: .wikicommit/scripts/skill_workflow.py does not exist; no run can be checked")
        return 0
    result = run([sys.executable, str(engine), "check-merge", "--except-run", args.run])
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError:
        print((result.stdout + result.stderr).strip() or f"check-merge exited {result.returncode}")
        return 1
    if not response.get("blocked"):
        if result.returncode == 0:
            return 0
        print(response.get("error") or f"check-merge exited {result.returncode}")
        return 1
    for entry in response.get("open_runs", []):
        where = entry.get("step", "?") + (f" for {entry['item']}" if entry.get("item") else "")
        print(f"OPEN_RUN: {entry.get('run')} ({entry.get('skill')}) stopped at {where}; "
              f"files: {', '.join(entry.get('files', []))}")
    print("An unfinished run touched files in this change: finish it with `skill_workflow.py "
          "next <run>`, or have a person decide about its files and close it with "
          "`skill_workflow.py "
          "abandon <run> --reason <why>`")
    return 1


# --- Step 2: classify the changes (script steps, one list each) ---------------
#
# Each list is computed from `git status` and the files on disk, so a step that is
# run again gives the same answer; the engine keeps each one in the run record, so
# the `commit` step reads them instead of computing them again.

# Wiki pages: what every per-file quality check reads. Assets, the policy files, the
# review records and relations.yml are carried by the merge but are not pages, and
# each per-file check would fail on them.
PAGE_PATHSPECS = (".wikicommit/entity/**/*.md", ".wikicommit/view/**/*.md")
SOURCE_PATHSPECS = (".wikicommit/source/**/*.md",)
# `**` matches one or more directory levels in a `git status` pathspec, never zero,
# so the files directly under schema/ need a pathspec of their own.
SCHEMA_PATHSPECS = (".wikicommit/schema/*.md", ".wikicommit/schema/**/*.md")
VOCAB_FILE = ".wikicommit/schemaorg-vocab.json"
POLICY_FILES = (".wikicommit/source-policy.md", ".wikicommit/entity-policy.md")
RELATIONS_FILE = ".wikicommit/relations.yml"


# `run()` reads git with `errors="replace"`, so a path whose name is not valid UTF-8
# arrives holding U+FFFD and names no file on disk. Each caller handles such a path
# explicitly instead of letting `Path.is_file()` drop it without a word.
UNDECODABLE = "\ufffd"


class Halt(Exception):
    """A classification that must stop the merge; the message is the reason."""


def shown(path: str) -> str:
    """A path that holds U+FFFD, printable under any console encoding."""
    return path.replace(UNDECODABLE, "?")


def page_entries() -> list[tuple[str, str]] | None:
    """`porcelain(PAGE_PATHSPECS)`, halting on a page whose name is not valid UTF-8.

    Dropping it would not leave it out of the merge: the commit step stages by
    pathspec, so the page would be committed without any quality check reading it.
    A page's file name is a language-neutral English identifier, so no proper use
    meets this; the person renames the file.
    """
    found = porcelain(PAGE_PATHSPECS)
    if found is None:
        return None
    # A deleted page needs no check, and halting on it would leave no way out: a
    # tracked page renamed with a plain `mv` stays behind as ` D <old name>`.
    bad = [path for code, path in found if UNDECODABLE in path and "D" not in code]
    if bad:
        raise Halt("\n".join(
            [f"ERROR: {shown(path)}: the file name is not valid UTF-8, so no quality "
             "check can read this page" for path in bad]
            + ["Rename the file to a UTF-8 name (page file names are language-neutral "
               "English identifiers, e.g. yamada-taro.md) and run /wikicommit-merge again"]))
    return found


def pages() -> list[str] | None:
    """Changed wiki pages that are on disk. A deleted file (`D`) has no frontmatter
    to validate; removal is `status: removed`, never a deleted file."""
    found = page_entries()
    if found is None:
        return None
    return [path for code, path in found if "D" not in code and Path(path).is_file()]


def removing() -> list[str] | None:
    """Changed pages that say `status: removed` now and did not at HEAD. A page new
    in this change is not being removed."""
    found = page_entries()
    if found is None:
        return None
    out = []
    for code, path in found:
        # An untracked page has no HEAD version to compare with: skip the `git show`.
        if code == "??" or "D" in code or not Path(path).is_file():
            continue
        head = run(["git", "show", f"HEAD:{path}"])
        if head.returncode != 0:
            continue
        before, _ = parse_frontmatter_text(head.stdout)
        if isinstance(before, dict) and before.get("status") == "removed":
            continue
        if read_markdown(Path(path))[0].get("status") == "removed":
            out.append(path)
    return out


def new_sources() -> tuple[list[str], list[str]] | None:
    """The source files `wikicommit-generate` registered and never commits itself:
    a changed management file's `source.path`, when that file is untracked.

    Existence is checked before `git status`, because `git status` prints nothing
    both for a path that is tracked and unchanged and for one that does not exist.
    The path goes to git as `:(literal)`, so `[2024]` is not a character class.
    `--ignored`, because without it an ignored file also prints nothing.
    """
    found = porcelain(SOURCE_PATHSPECS)
    if found is None:
        return None
    items: list[str] = []
    seen: set[str] = set()
    warnings: list[str] = []
    for code, manager in found:
        if "D" in code:
            continue
        if UNDECODABLE in manager:
            # The commit step stages .wikicommit/source/ whole, so this management
            # file is committed even though nothing here can read its source.path.
            warnings.append(f"WARNING: {shown(manager)}: the management file's name is "
                            "not valid UTF-8, so its source.path cannot be read and the "
                            "source file it names will not be included in the commit — "
                            "rename it to a UTF-8 name")
            continue
        source = read_markdown(Path(manager))[0].get("source")
        if not isinstance(source, dict) or source.get("type") != "path":
            continue
        path = source.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        if not Path(path).exists():
            warnings.append(f"WARNING: {manager}: source.path ({path}) does not exist")
            continue
        status = porcelain([f":(literal){path}"], ignored=True)
        if not status:
            continue  # tracked and unchanged: committed for another purpose already
        # A directory `source.path` (only a hand-written management file has one)
        # lists one entry per file, in no order to rely on: each is judged on its
        # own, and only the untracked files are carried — never the directory, whose
        # `git add` would also stage tracked files' unrelated edits.
        ignored = []
        for code, entry in status:
            if code == "??" and UNDECODABLE in entry:
                # Not a page: a source file can fairly have such a name (a Shift_JIS
                # zip unpacked on Linux), so it is left out with a warning, as an
                # ignored file is, rather than stopping the whole merge. Only an
                # untracked one: an ignored one gets the .gitignore warning below, and
                # a tracked one is left alone like any other tracked file.
                warnings.append(f"WARNING: {manager}: source.path ({path}) holds a file "
                                f"whose name is not valid UTF-8 ({shown(entry)}); it will "
                                "not be included in the commit — rename it to a UTF-8 "
                                "name to carry it")
            elif code == "??":
                if entry not in seen:
                    seen.add(entry)
                    items.append(entry)
            elif code == "!!":
                ignored.append(entry)
            # Tracked with uncommitted changes: deliberately left alone, so that
            # unrelated code changes are never swept into a wiki commit.
        if ignored:
            # git prints `raw/x.pdf` for `./raw/x.pdf` and `raw/dir` for `raw/dir/`.
            same = [norm(entry) for entry in ignored] == [norm(path)]
            what = path if same else f"{path}: {', '.join(shown(e) for e in ignored)}"
            warnings.append(f"WARNING: {manager}: source.path ({what}) is excluded by "
                            ".gitignore and will not be included in the commit")
    return items, warnings


def new_schema() -> tuple[list[str], list[str]] | None:
    """Type files written by generate's Pass 2b or collect, never committed yet.
    An edit to a committed one is never carried by an auto-merged batch."""
    found = porcelain(SCHEMA_PATHSPECS)
    if found is None:
        return None
    items, warnings = [], []
    for code, path in found:
        if code == "??":
            items.append(path)
        else:
            warnings.append(
                f"WARNING: {path}: an existing schema file has uncommitted changes and "
                "will not be included in this batch — .wikicommit/schema/ edits to "
                "already-committed files are never auto-merged (only a "
                "separately-reviewed schema proposal PR touches an existing schema "
                "file)")
    return items, warnings


def new_vocab() -> list[str] | None:
    """The Schema.org vocabulary, only when it was built for the first time. A
    rebuilt tracked copy is a content update for a person to commit."""
    found = porcelain([VOCAB_FILE])
    if found is None:
        return None
    return [path for code, path in found if code == "??"]


def present(pathspecs) -> list[str] | None:
    """Every path that shows as changed at all. For the policy files and
    relations.yml a modified tracked file is the normal case: every write after the
    first is an in-place edit, and nothing else in WikiCommit commits them."""
    found = porcelain(pathspecs)
    return None if found is None else [path for _, path in found]


CLASSIFIERS = {
    "pages": pages,
    "removing": removing,
    "sources": new_sources,
    "schema": new_schema,
    "vocab": new_vocab,
    "policy": lambda: present(POLICY_FILES),
    "relations": lambda: present([RELATIONS_FILE]),
}


def cmd_classify(args) -> int:
    """One of Step 2's lists, one `ITEM:` per path. Warnings are shown, never stop;
    a page whose name is not valid UTF-8 does (exit 1, which halts the run)."""
    try:
        result = CLASSIFIERS[args.kind]()
    except Halt as e:
        print(e)
        return 1
    if result is None:
        print("git status failed; is this a Git repository?")
        return 1
    items, warnings = result if isinstance(result, tuple) else (result, [])
    for line in warnings:
        print(line)
    for item in items:
        print(f"ITEM: {item}")
    return 0


def cmd_list(args) -> int:
    """A list the run holds, one value per line (`-0`: NUL-separated, for `xargs -0`)."""
    values = listed(read_state(args.run), args.list)
    if args.null:
        sys.stdout.write("".join(f"{v}\0" for v in values))
    else:
        for value in values:
            print(value)
    return 0


# --- Step 3: the quality checks -----------------------------------------------
#
# What each tool found is kept beside the run, one JSON file per tool, under
# `.wikicommit/.cache/merge/<run>/`: rebuilt by running the checks again, and
# ignored by Git. The run record's `warnings` list holds one `<tool> (<count>)` line
# per tool; the PR body is built from the files by `pr-body`.

# (name, blocking prefixes, warning prefixes), in the order the checks run and the
# PR body lists them. lychee and markdownlint-cli2 never block.
TOOLS = (
    ("validate_frontmatter.py", ("ERROR:",), ("WARNING:",)),
    ("check_wikilinks.py", ("ERROR:",), ("WARNING:",)),
    ("check_raw_html.py", ("ERROR:",), ("WARNING:",)),
    ("lychee", (), ()),
    ("markdownlint-cli2", (), ()),
    ("check_orphans.py", ("DUPLICATE:",), ("ORPHAN:",)),
)
SCRIPTS_DIR = Path(".wikicommit/scripts")
CACHE_DIR = Path(".wikicommit/.cache")
# Findings per tool shown in the PR body; the count carries the rest.
SAMPLES = 5
# Keep each command line well under Windows' 32,767 characters.
ARGV_CHARS = 20000


def findings_dir(run_path: str) -> Path:
    return CACHE_DIR / "merge" / Path(run_path).stem


def write_findings(run_path: str, tool: str, findings: list[str]) -> None:
    directory = findings_dir(run_path)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{tool}.json").write_text(
        json.dumps({"tool": tool, "findings": findings}, ensure_ascii=False, indent=1),
        encoding="utf-8")


def read_findings(run_path: str, tool: str) -> list[str] | None:
    """The tool's findings, or None when the tool has not recorded any run."""
    try:
        data = json.loads((findings_dir(run_path) / f"{tool}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    values = data.get("findings") if isinstance(data, dict) else None
    return [str(v) for v in values] if isinstance(values, list) else None


def chunks(paths: list[str], limit: int = ARGV_CHARS):
    """The paths in groups whose total length fits `limit` characters."""
    group: list[str] = []
    size = 0
    for path in paths:
        if group and size + len(path) + 1 > limit:
            yield group
            group, size = [], 0
        group.append(path)
        size += len(path) + 1
    if group:
        yield group


def argv_length(argv: list[str]) -> int:
    """The characters `argv` takes on a command line, a separator after each."""
    return sum(len(arg) + 1 for arg in argv)


def path_argvs(prefix: list[str], paths: list[str], limit: int = ARGV_CHARS):
    """`prefix` followed by the paths in groups, each whole command line within
    `limit` characters (Issue #1263). The prefix — interpreter, script path and any
    flag — is counted against `limit`, not only the paths after it. A single path
    too long to fit still gets a call of its own rather than being dropped."""
    return [[*prefix, *group]
            for group in chunks(paths, limit - argv_length(prefix))]


def wikilink_argvs(prefix: list[str], changed: list[str], removed: list[str],
                   limit: int = ARGV_CHARS):
    """`check_wikilinks.py` calls, each within `limit`: the changed pages' own
    links with `--changed` alone, one call per group of changed pages, and the
    backlinks left to the removed pages with `--deleted` alone, one call per group
    of removed pages (Issue #1257).

    The two checks do not depend on each other, so they are not crossed: a page is
    checked by exactly one call of each kind, and every call reads the wiki once —
    m + k calls rather than m x k, none of which repeats another's finding. A
    removed page is in `changed` too, and gets both checks.
    """
    return (path_argvs([*prefix, "--changed"], changed, limit)
            + path_argvs([*prefix, "--deleted"], removed, limit))


def run_script(argvs: list[list[str]], blocking: tuple, warning: tuple):
    """(blocking lines, warning lines, crash) over every invocation. A blocking
    finding is decided by what the script printed, not by its exit code — but a
    script that exits other than 0 or 1 without printing one did not run at all,
    and that must not pass as a clean result."""
    blocked, warned = [], []
    for argv in argvs:
        result = run(argv)
        lines = [line.strip() for line in (result.stdout + "\n" + result.stderr).splitlines()]
        found = [line for line in lines if line.startswith(blocking)] if blocking else []
        blocked.extend(found)
        warned.extend(line for line in lines if warning and line.startswith(warning))
        # An uncaught Python exception also exits 1, so a traceback is a crash too.
        crashed = result.returncode not in (0, 1) or (
            result.returncode == 1 and "Traceback (most recent call last):" in result.stderr)
        if crashed and not found:
            last = next((line for line in reversed(lines) if line), f"exit {result.returncode}")
            return dedup(blocked), dedup(warned), f"could not run ({last})"
    # A finding printed by more than one call (a script whose output does not
    # depend on its share of the paths) is reported once, as from one call.
    return dedup(blocked), dedup(warned), ""


def dedup(lines: list[str]) -> list[str]:
    return list(dict.fromkeys(lines))


def cmd_checks(args) -> int:
    """The fast checks: frontmatter, WikiLinks, raw HTML and orphans/duplicates.

    Stops at the first check that prints a blocking finding (exit 1, which halts the
    run before any branch exists). With no changed page, the three per-file checks
    are skipped rather than called with no paths: each reads "no paths" as "every
    page in the wiki", which would block this change on pages it never touched.
    """
    state = read_state(args.run)
    changed = listed(state, "changed_md")
    removed = listed(state, "removing")
    python = sys.executable
    plans = {
        "validate_frontmatter.py": path_argvs(
            [python, str(SCRIPTS_DIR / "validate_frontmatter.py")], changed),
        "check_wikilinks.py": wikilink_argvs(
            [python, str(SCRIPTS_DIR / "check_wikilinks.py")], changed, removed),
        "check_raw_html.py": path_argvs(
            [python, str(SCRIPTS_DIR / "check_raw_html.py")], changed),
        "check_orphans.py": [[python, str(SCRIPTS_DIR / "check_orphans.py")]],
    }
    for tool, blocking, warning in TOOLS:
        if tool not in plans:
            continue
        blocked, warned, crash = run_script(plans[tool], blocking, warning)
        if blocked or crash:
            for line in blocked:
                print(line)
            print(f"BLOCKED: {tool}: {blocked[0] if blocked else crash}")
            return 1
        write_findings(args.run, tool, warned)
        if warned:
            print(f"{tool}: {len(warned)} warning(s)")
    return 0


def cmd_links(args) -> int:
    """External links of the changed pages, a few pages per lychee call, returning
    within about `--limit` seconds however many pages there are.

    The agent's shell has a time limit (Claude Code's Bash defaults to 120 seconds)
    and one link can take 10 s × 3 attempts. So this checks pages in small batches,
    starts no new batch after `--budget` seconds, and keeps what it has done beside
    the run: calling it again continues where the last call stopped. lychee runs
    inside `.wikicommit/.cache/lychee/`, so its `--cache` file lands there (ignored
    by Git) and is shared by later merges and by `/wikicommit-status`. The batching
    itself is `check_external_links.check_link_batches()`, which status's check of
    every page uses too (Issue #1182). It returns structured findings; the run's
    `lychee.json` keeps their text only, as the other tools' files do, since the PR
    body lists text and nothing here tells a broken link from an unchecked one
    (Issue #1243).
    """
    changed = listed(read_state(args.run), "changed_md")
    checked, findings, remaining = check_link_batches(
        changed, findings_dir(args.run) / "lychee-progress.json",
        batch=args.batch, budget=args.budget, limit=args.limit, what="changed pages")
    print(f"LINKS: {len(checked)}/{len(changed)} changed page(s) checked")
    if remaining:
        print("LINKS: more — run this same command again")
        return 0
    write_findings(args.run, "lychee", [f["text"] for f in findings])
    print(f"LINKS: done, {len(findings)} warning(s)")
    return 0


def cmd_style(args) -> int:
    """Record what markdownlint-cli2 printed (piped in on stdin, stderr included).

    markdownlint runs in the agent's shell, through `xargs`, rather than from here:
    `npx` is `npx.cmd` on Windows, which Python cannot start without a shell. Output
    with no finding and no `Summary:` line means it never ran; that is recorded as a
    warning instead of passing as a clean result.
    """
    text = sys.stdin.read()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    findings = [line for line in lines
                if re.search(r"\bMD\d{3}\b", line) and re.search(r":\d+", line)]
    if not findings and not any(line.startswith("Summary:") for line in lines):
        first = lines[0] if lines else "no output"
        findings = [f"markdownlint-cli2 did not run: {first}"]
    write_findings(args.run, "markdownlint-cli2", findings)
    print(f"markdownlint-cli2: {len(findings)} finding(s)")
    return 0


def cmd_check_slow(args) -> int:
    """lychee has seen every changed page and markdownlint's output was recorded.

    The step's `when:` skips it when `changed_md` is empty, so this check is only
    reached with pages to check."""
    if read_findings(args.run, "lychee") is None:
        print("lychee has not checked every changed page; run `workflow_checks.py links` "
              "again until it prints `LINKS: done`")
        return 1
    if read_findings(args.run, "markdownlint-cli2") is None:
        print("markdownlint-cli2's output was not recorded; pipe it into "
              "`workflow_checks.py style`")
        return 1
    return 0


def cmd_warnings(args) -> int:
    """One `ITEM: <tool> (<count>)` per tool that found anything."""
    for tool, _, _ in TOOLS:
        findings = read_findings(args.run, tool) or []
        if findings:
            print(f"ITEM: {tool} ({len(findings)})")
    return 0


def cmd_pr_body(args) -> int:
    """The PR body: what the checks found, a few findings per tool."""
    sections = []
    total = 0
    # The run record's `warnings` list (`<tool> (<count>)`) outlives the findings
    # files, which sit in an ignored cache: a tool it names whose file is gone must
    # not turn into "no warnings".
    recorded = {}
    for entry in listed(read_state(args.run), "warnings"):
        match = re.fullmatch(r"(.+) \((\d+)\)", entry)
        if match:
            recorded[match.group(1)] = int(match.group(2))
    for tool, _, _ in TOOLS:
        findings = read_findings(args.run, tool)
        if findings is None and recorded.get(tool):
            count = recorded[tool]
            total += count
            sections.append(f"### {tool} ({count})\n\n- (the findings are no longer "
                            "available on this machine; re-run the quality checks to "
                            "see them)")
            continue
        findings = findings or []
        if not findings:
            continue
        total += len(findings)
        lines = [f"### {tool} ({len(findings)})", ""]
        lines += [f"- {finding}" for finding in findings[:SAMPLES]]
        if len(findings) > SAMPLES:
            lines.append(f"- (+{len(findings) - SAMPLES} more)")
        sections.append("\n".join(lines))
    out = ["Automatically generated PR by WikiCommit.", ""]
    if not sections:
        out.append("Quality checks ran with no blocking errors and no warnings.")
    else:
        out += [f"Quality checks ran with no blocking errors. Warnings: {total}.", "",
                "## Warnings", "", "\n\n".join(sections), "",
                "Only the first few findings per tool are listed here. Re-running "
                "WikiCommit's quality checks reproduces the full list."]
    print("\n".join(out))
    return 0


# --- conditions ---------------------------------------------------------------


def cmd_has_list(args) -> int:
    if listed(read_state(args.run), args.list):
        return 0
    print(f"the run record's {args.list!r} list is empty")
    return 1


# --- step checks --------------------------------------------------------------


def cmd_check_commit(args) -> int:
    """On a merge branch, with a commit of its own, and nothing left uncommitted."""
    state = read_state(args.run)
    branch = current_branch()
    if not branch.startswith(BRANCH_PREFIX):
        print(f"the current branch is {branch or 'unknown'!r}, not a {BRANCH_PREFIX}* branch")
        return 1
    base = default_branch(state)
    for ref in (base, f"origin/{base}"):
        if run(["git", "rev-parse", "--verify", "--quiet", ref]).returncode == 0:
            count = run(["git", "rev-list", "--count", f"{ref}..HEAD"]).stdout.strip()
            if count in ("", "0"):
                print(f"{branch} has no commit beyond {ref}")
                return 1
            break
    left = changed_paths()
    if left is None:
        print("git status failed")
        return 1
    if left:
        print("these changes are still uncommitted: " + ", ".join(left))
        return 1
    return 0


def cmd_check_pr(args) -> int:
    """A PR number was recorded and the branch it came from is on the remote."""
    state = read_state(args.run)
    numbers = listed(state, "pr")
    if not numbers or not numbers[-1].lstrip("#").isdigit():
        print("no PR number was recorded; pass --add pr=<PR number>")
        return 1
    branch = current_branch()
    result = run(["git", "ls-remote", "--heads", "origin", f"refs/heads/{branch}"])
    if result.returncode != 0 or not result.stdout.strip():
        print(f"{branch} is not on origin; push it before opening the PR")
        return 1
    return 0


def cmd_check_merged(args) -> int:
    """GitHub says the PR is merged, and the default branch is checked out."""
    state = read_state(args.run)
    numbers = listed(state, "pr")
    if not numbers:
        print("no PR number was recorded")
        return 1
    number = numbers[-1].lstrip("#")
    result = run(["gh", "pr", "view", number, "--json", "state", "-q", ".state"])
    status = result.stdout.strip()
    if result.returncode != 0:
        print(f"gh could not read PR {number}: {(result.stderr or result.stdout).strip()}")
        return 1
    if status != "MERGED":
        print(f"PR {number} is {status or 'in an unknown state'}, not MERGED")
        return 1
    base = default_branch(state)
    if current_branch() != base:
        print(f"the merge went through; check out and pull {base!r} before reporting it")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="wikicommit-merge workflow checks")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, run_arg=True, **extra):
        p = sub.add_parser(name)
        if run_arg:
            p.add_argument("--run", required=True)
        for flag, default in extra.items():
            p.add_argument(f"--{flag.replace('_', '-')}", default=default)
        p.set_defaults(func=func)

    add("freshness", cmd_freshness, run_arg=False)
    add("default-branch", cmd_default_branch, run_arg=False)
    add("detect", cmd_detect, run_arg=False)
    add("open-runs", cmd_open_runs)
    p = sub.add_parser("classify")
    p.add_argument("--kind", required=True, choices=sorted(CLASSIFIERS))
    p.set_defaults(func=cmd_classify)
    p = sub.add_parser("list")
    p.add_argument("--run", required=True)
    p.add_argument("--list", required=True)
    p.add_argument("-0", "--null", action="store_true")
    p.set_defaults(func=cmd_list)
    add("checks", cmd_checks)
    p = sub.add_parser("links")
    p.add_argument("--run", required=True)
    p.add_argument("--batch", type=int, default=5)
    p.add_argument("--budget", type=float, default=45.0)
    p.add_argument("--limit", type=float, default=100.0)
    p.set_defaults(func=cmd_links)
    add("style", cmd_style)
    add("check-slow-checks", cmd_check_slow)
    add("warnings", cmd_warnings)
    add("pr-body", cmd_pr_body)
    add("has-list", cmd_has_list, list="warnings")
    add("check-commit", cmd_check_commit)
    add("check-pr", cmd_check_pr)
    add("check-merged", cmd_check_merged)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
