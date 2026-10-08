#!/usr/bin/env python3
"""workflow_checks.py — the wikicommit-generate knowledge `skill_workflow.py` does not have.

`skill_workflow.py` knows how to walk a workflow and nothing about this Skill. What a
step's completion looks like on disk — which frontmatter field a pass writes,
which section a deferral leaves, where a review record lands — lives here, next
to `workflow.yaml`, so the engine stays usable by another Skill.

Every subcommand runs from the repository root and follows one contract:

- **exit 0** means yes (a condition holds, a check passed, a list was produced)
- **exit 1** means no, with the reason on stdout
- `ITEM: <value>` lines are a produced list, `TOUCHED: <path>` lines are files the
  check confirmed the step wrote

These checks confirm consistency, not proof. A pass that writes nothing it did not
already write on an earlier run cannot be told from one that did not run; what
they catch is the step that was forgotten, not one that was faked.
"""

import argparse
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
# it has none until `/wikicommit-update` is merged.
# Exit 2, not 1, whatever is missing: a `when:` condition exiting 1 would read as
# "skip this step", while 2 stops the engine. Only a module of `.wikicommit/scripts/`
# is fixed by `/wikicommit-update`; a missing PyYAML is not, so it gets its own
# pointer. This bootstrap cannot live in the module it loads, so each Skill carries it;
# tests/test_workflow_checks_shared.py holds the four copies to one shape.
sys.path.insert(0, str(Path.cwd() / ".wikicommit" / "scripts"))
try:
    from _workflow_checks import (
        cmd_over_cap, cmd_select, listed, norm, read_markdown, read_run, review_record_dir, run,
    )
except ImportError as e:
    if isinstance(e, ModuleNotFoundError) and e.name == "yaml":
        print(f"PyYAML is not installed ({e}); install it (pip install pyyaml) and run again")
    else:
        print(".wikicommit/scripts/ is missing a module this Skill needs or is older than "
              f"this Skill ({e}); run /wikicommit-update first")
    sys.exit(2)

SOURCE_DIR = Path(".wikicommit/source")

COLLECTED_STATUSES = ("pending", "outdated")
FINAL_STATUSES = ("generated", "partial", "excluded", "failed")


def run_arguments(record: dict) -> list[str]:
    args = record.get("args")
    return [str(a) for a in args] if isinstance(args, list) else []


def has_section(body: str, heading: str) -> bool:
    return any(line.strip() == heading for line in body.splitlines())


def section_text(body: str, heading: str) -> str:
    """The text under `heading` up to the next `## ` heading, stripped ("" if absent)."""
    lines, inside = [], False
    for line in body.splitlines():
        if line.strip() == heading:
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if inside:
            lines.append(line)
    return "\n".join(lines).strip()


# The first-loop steps whose deferral is a question for a person, and the reason
# line that marks guard A's (Pass 1 also defers on NETWORK_UNAVAILABLE, which
# waits for a network, not a person).
QUESTION_STEPS = ("pass1-extract", "pass2b-type")
LOW_DENSITY = "LOW_DENSITY:"
NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE:"
# A type candidate as Pass 2b writes it into its `## Deferred Reason`.
TYPE_NAME = re.compile(r"schema:[A-Za-z][A-Za-z0-9_]*")


def _deferral_reason(path: str) -> str:
    _, body = read_markdown(Path(path))
    return section_text(body, "## Deferred Reason")


def deferred_questions(state: dict) -> dict[str, str]:
    """{management file: the step that deferred it} for every source this run set
    aside for a person's answer, in the order they were deferred."""
    found: dict[str, str] = {}
    log = state.get("log")
    for entry in log if isinstance(log, list) else []:
        if not (isinstance(entry, dict) and entry.get("outcome") == "deferred"
                and entry.get("step") in QUESTION_STEPS and entry.get("item")):
            continue
        item = str(entry["item"])
        reason = _deferral_reason(item)
        if not reason:
            continue
        if entry["step"] == "pass1-extract" and not reason.startswith(LOW_DENSITY):
            continue
        found.setdefault(norm(item), str(entry["step"]))
    return found


# --- conditions ---------------------------------------------------------------


def cmd_has_source_argument(args) -> int:
    """True when the run was given a source to register (Step 0 applies)."""
    record, _ = read_run(args.run)
    values = run_arguments(record)
    skip_next = False
    for value in values:
        if skip_next:
            skip_next = False
            continue
        if value == "--include":
            skip_next = True
            continue
        if not value.startswith("--"):
            return 0
    print("no source argument; Step 0 does not apply")
    return 1


# --- preflight ----------------------------------------------------------------


# Scripts this Skill calls from `.wikicommit/scripts/` that used to live in a Skill's own
# `scripts/` (Issue #1210). A wiki whose `.wikicommit/scripts/` predates the move has none
# of them until `/wikicommit-update` is merged, and Step 0 would fail on the first command.
MOVED_SCRIPTS = ("add_source.py", "resolve_source_cache_path.py", "remove_page.py")


def cmd_preflight(args) -> int:
    """Stop before anything is fetched when the run could never finish."""
    if not Path(".wikicommit/config.yml").is_file():
        print(".wikicommit/config.yml does not exist; run /wikicommit-init first")
        return 1
    if not Path(".wikicommit/review-rules.md").is_file():
        print(".wikicommit/review-rules.md does not exist; run /wikicommit-init "
              "--no-overwrite to install it (Pass 4 cannot review without it)")
        return 1
    missing = [name for name in MOVED_SCRIPTS
               if not (Path(".wikicommit/scripts") / name).is_file()]
    if missing:
        print(f".wikicommit/scripts/{missing[0]} does not exist (.wikicommit/scripts/ is older "
              "than this Skill); run /wikicommit-update first")
        return 1
    return 0


def cmd_freshness(args) -> int:
    """Warn when `.wikicommit/scripts/` is out of step with this Skill. Never stops.

    Runs the copy in the Skill tree, not the one under `.wikicommit/scripts/`: the
    latter is the half that may be stale, and a detector shipped in the stale half
    is the bug it is looking for. No Skill tree copy means nothing to compare
    against, so it says nothing.
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


# --- lists --------------------------------------------------------------------


def _collectable(front: dict) -> bool:
    status = str(front.get("status") or "")
    if status in COLLECTED_STATUSES:
        return True
    failed = front.get("failed_pages")
    return status == "partial" and isinstance(failed, list) and bool(failed)


def _tier(front: dict, body: str) -> tuple[int, int]:
    if str(front.get("status") or "") == "outdated":
        tier = 0
    elif not front.get("last_generated_at"):
        tier = 1
    else:
        tier = 2
    return tier, 1 if has_section(body, "## Deferred Reason") else 0


def cmd_collect(args) -> int:
    """The management files this run will process, in processing order."""
    _, state = read_run(args.run)
    registered = state.get("lists", {}).get("registered")
    if registered:
        for path in registered:
            print(f"ITEM: {path}")
        return 0
    if not SOURCE_DIR.is_dir():
        return 0
    found = []
    for path in sorted(SOURCE_DIR.rglob("*.md")):
        front, body = read_markdown(path)
        if front and _collectable(front):
            found.append((_tier(front, body), path.as_posix()))
    for _, path in sorted(found):
        print(f"ITEM: {path}")
    return 0


def cmd_collect_questions(args) -> int:
    """The sources this run deferred for a person's answer (the end-of-loop question)."""
    _, state = read_run(args.run)
    for path in deferred_questions(state):
        print(f"ITEM: {path}")
    return 0


def cmd_has_list(args) -> int:
    _, state = read_run(args.run)
    if listed(state, args.list):
        return 0
    print(f"the run's {args.list} list is empty")
    return 1


# --- step checks --------------------------------------------------------------


def cmd_check_answers(args) -> int:
    """The answers handed back from `ask-deferred` fit the questions that were asked."""
    _, state = read_run(args.run)
    questions = deferred_questions(state)
    reprocess = [norm(p) for p in listed(state, "reprocess")]
    keep = [norm(p) for p in listed(state, "continue-low-density")]
    fail = [norm(p) for p in listed(state, "fail-low-density")]
    approved = listed(state, "approved-types")
    declined = listed(state, "declined-types")
    if args.answer == "later":
        if any((reprocess, keep, fail, approved, declined)):
            print("`later` leaves every deferral queued; pass no --add with it")
            return 1
        return 0
    problems = []
    if not reprocess:
        problems.append("name each source whose questions were all answered with "
                        "--add reprocess=<management file>")
    low_density = [p for p, step in questions.items() if step == "pass1-extract"]
    for path in reprocess:
        if path not in questions:
            problems.append(f"{path} was not deferred for a question in this run")
        elif path in low_density and path not in keep + fail:
            problems.append(f"{path} is a low-density question with no answer; add it to "
                            "continue-low-density or fail-low-density")
    for path in keep + fail:
        if path not in low_density:
            problems.append(f"{path} was not deferred by the low-density check in this run")
        elif path not in reprocess:
            problems.append(f"{path} has a low-density answer but is not in reprocess")
    both = sorted(set(keep) & set(fail))
    if both:
        problems.append("both continued and failed: " + ", ".join(both))
    both = sorted(set(approved) & set(declined))
    if both:
        problems.append("both approved and declined: " + ", ".join(both))
    twice = sorted({p for p in reprocess if reprocess.count(p) > 1})
    if twice:
        problems.append("named more than once in reprocess: " + ", ".join(twice))
    # Matched as whole names, not substrings: Pass 2b looks its candidate up in
    # these lists by name, so `schema:Government` would never match a deferral on
    # `schema:GovernmentService` and the source would only be deferred again.
    candidates = {p: set(TYPE_NAME.findall(_deferral_reason(p)))
                  for p, step in questions.items() if step == "pass2b-type"}
    proposed = set().union(*candidates.values()) if candidates else set()
    for name in approved + declined:
        if name not in proposed:
            problems.append(f"{name} is not a type candidate any source deferred on in this run")
    answered_types = set(approved) | set(declined)
    for path in reprocess:
        if path in candidates and not candidates[path] & answered_types:
            problems.append(f"{path} is in reprocess but none of its type candidates was answered")
    if problems:
        print("; ".join(problems))
        return 1
    return 0


def cmd_check_register(args) -> int:
    _, state = read_run(args.run)
    if args.outcome == "nothing":
        return 0
    registered = state.get("lists", {}).get("registered", [])
    if not registered:
        print("no management file was named; pass --add registered=<management file> "
              "for each file add_source.py reported")
        return 1
    missing = [p for p in registered
               if not (Path(p).is_file() and Path(p).resolve().is_relative_to(SOURCE_DIR.resolve()))]
    if missing:
        print("not a management file under .wikicommit/source/: " + ", ".join(missing))
        return 1
    for path in registered:
        print(f"TOUCHED: {path}")
    return 0


def cmd_check_pass1(args) -> int:
    path = Path(args.item)
    front, body = read_markdown(path)
    if not front:
        print(f"{path}: cannot read the management file")
        return 1
    # A low-density answer from the end-of-loop question has to be carried out,
    # not met with the same deferral again.
    if args.run:
        _, state = read_run(args.run)
        item = norm(args.item)
        if item in map(norm, listed(state, "fail-low-density")) and args.outcome != "failed":
            print(f"{path}: the person chose not to continue with this source; "
                  "mark it failed (outcome `failed`)")
            return 1
        if (item in map(norm, listed(state, "continue-low-density")) and args.outcome == "deferred"
                and section_text(body, "## Deferred Reason").startswith(LOW_DENSITY)):
            print(f"{path}: the person chose to continue with this source; "
                  "treat the density check as passed")
            return 1
    if args.outcome == "extracted":
        tokens = front.get("extracted_tokens")
        if not isinstance(tokens, int) or tokens <= 0:
            print(f"{path}: extracted_tokens is not written")
            return 1
        if str(front.get("status") or "") == "failed":
            print(f"{path}: status is failed, which contradicts `extracted`")
            return 1
    elif args.outcome == "failed":
        if str(front.get("status") or "") != "failed" or not has_section(body, "## Failure Reason"):
            print(f"{path}: `failed` needs status: failed and a ## Failure Reason section")
            return 1
    elif args.outcome == "deferred":
        if not has_section(body, "## Deferred Reason"):
            print(f"{path}: `deferred` needs a ## Deferred Reason section")
            return 1
        # The end-of-loop question finds a low-density deferral by this prefix, so a
        # reason written any other way would be left queued without being asked.
        if not section_text(body, "## Deferred Reason").startswith(
                (LOW_DENSITY, NETWORK_UNAVAILABLE)):
            print(f"{path}: ## Deferred Reason must start with the script's "
                  f"`{LOW_DENSITY}` or `{NETWORK_UNAVAILABLE}` line, verbatim")
            return 1
    print(f"TOUCHED: {path}")
    return 0


def cmd_check_pass2b(args) -> int:
    path = Path(args.item)
    _, body = read_markdown(path)
    if args.outcome == "deferred" and not has_section(body, "## Deferred Reason"):
        print(f"{path}: `deferred` needs a ## Deferred Reason section")
        return 1
    return 0


def cmd_check_pass2c(args) -> int:
    path = Path(args.item)
    front, body = read_markdown(path)
    if not has_section(body, "## Summary"):
        print(f"{path}: ## Summary was not written back")
        return 1
    # `halted` (a second NETWORK_UNAVAILABLE in a row) defers this source the
    # same way before the run stops, so it is held to the same two conditions.
    if args.outcome in ("deferred", "halted"):
        if not has_section(body, "## Deferred Reason"):
            print(f"{path}: `{args.outcome}` needs a ## Deferred Reason section")
            return 1
        # A forced recheck already rewrote source.hash in Pass 1; left at
        # generated/failed/excluded (or partial with no failed_pages), the next
        # run would see HASH_MATCH and drop this update. The source has to stay
        # somewhere the queue collects.
        if not _collectable(front):
            print(f"{path}: a deferred source must stay queued; set status: pending (it is {front.get('status')!r})")
            return 1
    return 0


def cmd_check_pass4(args) -> int:
    """The management file reached a final status and every page it names exists
    and has a review record — the write-back that used to be patched up after the
    run instead of checked at the step."""
    path = Path(args.item)
    front, _ = read_markdown(path)
    status = str(front.get("status") or "")
    if status not in FINAL_STATUSES:
        print(f"{path}: status is {status or 'unset'}; Pass 4 has not written the final status")
        return 1
    # Only the two branches that record pages write last_generated_at; `excluded`
    # and `failed` do not, so requiring it there would refuse a correct write-back.
    if not front.get("last_generated_at") and status in ("generated", "partial"):
        print(f"{path}: last_generated_at is not written")
        return 1
    problems = []
    pages = front.get("generated_pages")
    pages = [str(p) for p in pages] if isinstance(pages, list) else []
    for page in pages:
        if not Path(page).is_file():
            problems.append(f"{page} is listed in generated_pages but does not exist")
        elif page.startswith(".wikicommit/") and not any(review_record_dir(page).glob("*.md")):
            problems.append(f"{page} has no review record under .wikicommit/review/")
    if problems:
        print(f"{path}: " + "; ".join(problems))
        return 1
    print(f"TOUCHED: {path}")
    for page in pages:
        print(f"TOUCHED: {page}")
    return 0


def cmd_check_page_exists(args) -> int:
    if not Path(args.item).is_file():
        print(f"{args.item}: the page is not on disk")
        return 1
    print(f"TOUCHED: {args.item}")
    return 0


def merge_arguments(record: dict) -> tuple[str, list[str]]:
    """(kept page, absorbed pages) from a `--regenerate <page> --merge <page>...` run.

    The kept page is the one positional argument not taken by `--merge` or
    `--type`; it is "" when the run is not a merge.
    """
    keep, absorb = "", []
    values = run_arguments(record)
    i = 0
    while i < len(values):
        value = values[i]
        if value in ("--merge", "--type") and i + 1 < len(values):
            if value == "--merge":
                absorb.append(values[i + 1])
            i += 2
            continue
        if not value.startswith("--") and not keep:
            keep = value
        i += 1
    return (keep, absorb) if absorb else ("", [])


def cmd_merge_ready(args) -> int:
    """True when this is a merge run and the kept page was rebuilt and written."""
    record, state = read_run(args.run)
    keep, absorb = merge_arguments(record)
    if not absorb:
        print("not a merge run")
        return 1
    for entry in state.get("log", []):
        if (isinstance(entry, dict) and entry.get("step") == "pass4-review"
                and entry.get("outcome") == "rebuilt" and Path(str(entry.get("item", ""))) == Path(keep)):
            return 0
    print(f"{keep} was not rebuilt, so nothing is absorbed into it")
    return 1


def cmd_check_merge(args) -> int:
    """The merge was carried through — delegated to merge_pages.py check."""
    record, _ = read_run(args.run)
    keep, absorb = merge_arguments(record)
    command = [sys.executable, ".wikicommit/scripts/merge_pages.py", "check", "--into", keep]
    for page in absorb:
        command += ["--absorb", page]
    result = run(command)
    print(result.stdout, end="")
    return 0 if result.returncode == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="wikicommit-generate workflow checks")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, run=True, item=False, outcome=False, **extra):
        p = sub.add_parser(name)
        if run == "optional":
            p.add_argument("--run", default="")
        elif run:
            p.add_argument("--run", required=True)
        if item:
            p.add_argument("--item", required=True)
        if outcome:
            p.add_argument("--outcome", default="")
        for flag, default in extra.items():
            p.add_argument(f"--{flag.replace('_', '-')}", default=default)
        p.set_defaults(func=func)

    add("preflight", cmd_preflight)
    add("freshness", cmd_freshness, run=False)
    add("has-source-argument", cmd_has_source_argument)
    add("over-cap", cmd_over_cap, list="candidates")
    add("collect", cmd_collect)
    add("select", cmd_select, list="candidates", answer_step="batch-cap")
    add("check-register", cmd_check_register, outcome=True)
    add("collect-questions", cmd_collect_questions)
    add("has-list", cmd_has_list, list="")
    add("check-answers", cmd_check_answers, answer="")
    add("check-pass1", cmd_check_pass1, run="optional", item=True, outcome=True)
    add("check-pass2b", cmd_check_pass2b, run=False, item=True, outcome=True)
    add("check-pass2c", cmd_check_pass2c, run=False, item=True, outcome=True)
    add("check-pass4", cmd_check_pass4, run=False, item=True)
    add("check-page-exists", cmd_check_page_exists, run=False, item=True)
    add("merge-ready", cmd_merge_ready)
    add("check-merge", cmd_check_merge)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
