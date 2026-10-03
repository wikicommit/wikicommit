#!/usr/bin/env python3
"""workflow_checks.py — the wikicommit-generate knowledge `driver.py` does not have.

`driver.py` knows how to walk a workflow and nothing about this Skill. What a
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
import subprocess
import sys
from pathlib import Path

import yaml

SOURCE_DIR = Path(".wikicommit/source")
REVIEW_DIR = Path(".wikicommit/review")
BATCH_CAP = 5

COLLECTED_STATUSES = ("pending", "outdated")
FINAL_STATUSES = ("generated", "partial", "excluded", "failed")


def read_markdown(path: Path) -> tuple[dict, str]:
    """Frontmatter and body. A file with no readable frontmatter gives `{}`."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return {}, ""
    if not text.startswith("---"):
        return {}, text
    _, _, rest = text.partition("---\n")
    front, sep, body = rest.partition("\n---")
    if not sep:
        return {}, text
    try:
        data = yaml.safe_load(front)
    except yaml.YAMLError:
        return {}, body
    return (data if isinstance(data, dict) else {}), body


def read_run(run: str) -> tuple[dict, dict]:
    record, _ = read_markdown(Path(run))
    state = record.get("driver") if isinstance(record.get("driver"), dict) else {}
    return record, state


def run_arguments(record: dict) -> list[str]:
    args = record.get("args")
    return [str(a) for a in args] if isinstance(args, list) else []


def answer_of(state: dict, step: str) -> str:
    for entry in state.get("log", []):
        if isinstance(entry, dict) and entry.get("step") == step and entry.get("answer"):
            return str(entry["answer"])
    return ""


def has_section(body: str, heading: str) -> bool:
    return any(line.strip() == heading for line in body.splitlines())


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


def cmd_over_cap(args) -> int:
    _, state = read_run(args.run)
    items = state.get("lists", {}).get(args.list, [])
    if len(items) > BATCH_CAP:
        return 0
    print(f"{len(items)} item(s); no more than {BATCH_CAP}, so nothing to ask")
    return 1


# --- preflight ----------------------------------------------------------------


def cmd_preflight(args) -> int:
    """Stop before anything is fetched when the run could never finish."""
    if not Path(".wikicommit/config.yml").is_file():
        print(".wikicommit/config.yml does not exist; run /wikicommit-init first")
        return 1
    if not Path(".wikicommit/review-rules.md").is_file():
        print(".wikicommit/review-rules.md does not exist; run /wikicommit-init "
              "--no-overwrite to install it (Pass 4 cannot review without it)")
        return 1
    return 0


def cmd_freshness(args) -> int:
    """Warn when `.wikicommit/scripts/` is out of step with this Skill. Never stops.

    Runs the copy in the Skill tree, not the one under `.wikicommit/scripts/`: the
    latter is the half that may be stale, and a detector shipped in the stale half
    is the bug it is looking for. No Skill tree copy means nothing to compare
    against, so it says nothing.
    """
    import subprocess

    here = Path(__file__).resolve().parent
    checker = (here.parent.parent / "wikicommit-init" / "scripts" / "templates"
               / "scripts" / "check_distribution_freshness.py")
    if not checker.is_file():
        return 0
    result = subprocess.run(
        [sys.executable, str(checker), "--only", ".wikicommit/scripts"],
        capture_output=True, text=True, check=False,
    )
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


def cmd_select(args) -> int:
    """Apply the batch-cap answer to the collected list."""
    _, state = read_run(args.run)
    items = list(state.get("lists", {}).get(args.list, []))
    if answer_of(state, args.answer_step) == "first-five":
        items = items[:BATCH_CAP]
    for item in items:
        print(f"ITEM: {item}")
    return 0


# --- step checks --------------------------------------------------------------


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


def review_record_dir(page: str) -> Path:
    rel = Path(page).relative_to(".wikicommit")
    return REVIEW_DIR / rel.with_suffix("")


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
    result = subprocess.run(command, capture_output=True, text=True)
    print(result.stdout, end="")
    return 0 if result.returncode == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="wikicommit-generate workflow checks")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, run=True, item=False, outcome=False, **extra):
        p = sub.add_parser(name)
        if run:
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
    add("check-pass1", cmd_check_pass1, run=False, item=True, outcome=True)
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
