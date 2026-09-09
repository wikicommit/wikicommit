#!/usr/bin/env python3
"""record_run.py — write one file per run of a Skill (Issue #790).

This repository has four record layers and every one of them is keyed on an
**artifact**: Git history on files, the source management files on one source,
the review records on one review of one page (Issue #750), the tracking Issues
on one page. Nothing is keyed on a **run**, and three questions follow from
that gap:

- **When was a page actually generated?** `generated_at` holds a date. A commit
  timestamp is the merge, not the generation. A review record's filename holds a
  second, but it is the second Pass 4 finished *looking at* the page, one to
  three LLM round-trips after Pass 3 wrote it. And moving `generated_at` to a
  timestamp would not fix this: Pass 3 writes several pages in one file-boundary
  output, so every page in a batch would carry the same second. **A per-page
  instant does not exist. The unit that exists is the run.**
- **Did the run finish?** When a run dies partway, some management files sit at
  `pending` and some at `generated` — indistinguishable from the backlog Issue
  #567 dealt with, where the queue simply never reached them. Worse, the two
  halt paths that stop everything (guard C in Issue #574, a `rules_version`
  mismatch in Issue #752) change no file at all, so they leave *no trace in Git*.
- **How long did it take?** Nowhere. The pilot procedure has had an empty
  "time per repository" column since it was written.

## One run is one file, and it is not tracked by Git

The shape is Issue #750's — one record per event, created rather than appended —
but the storage decision is the opposite one, and deliberately:

| Why review records are tracked | Run records |
|---|---|
| Measurement over the wiki's whole life; it cannot be built retroactively | Only "the last run" and "runs that did not finish" are ever read |
| Displayed on the published site (Issue #751) | Displayed nowhere; `convert_wikilinks.py` never walks this tree |
| The verdict bears on whether a page can be trusted | The outward shape of a run; not knowledge the wiki holds |

Tracking them would put a file into the PR of every single generate run, and —
because deleting a file in Git does not make it go away — would make retention
impossible to express. Not tracking them buys rotation, keeps `wikicommit-merge`
untouched, and keeps lychee and markdownlint out of it, since nothing here ever
appears in a diff.

They are not put under `.wikicommit/.cache/` either. That directory is for
derived data that can be rebuilt (`search_index.sqlite3`); a run record cannot
be. Issue #319 already moved `schemaorg-vocab.json` out of it for the mirror
image of this reason — that the name promises "safe to delete" about something
whose real nature is different.

What that costs, accepted in full: a cloud session's records die with the VM
(so do that run's uncommitted outputs, so the two stay consistent), a clone
sees nothing, and "when exactly was this page made" is answerable only as an
interval. The interval is all a tracked record could have offered either, per
the first bullet above.

## An empty `ended_at` is the answer, not a bug

`start` writes `ended_at: ""` and `end` fills it in. Forgetting the closing
stamp at the tail of a long multi-pass flow is the failure mode Issues #406,
#452 and #474 each had to fix once — and here it needs no fixing, because a
record with a start and no end *is* the answer to "did this run finish". This
is Issue #750's `page_content_hash: ""` meaning "no page was written", in the
same position.

The direction of the error matters: a forgotten stamp reports a completed run
as incomplete, never the reverse. A false "did not finish" costs a glance at a
run that was fine; a false "finished" would silently retire the one question
this file exists to answer. That is also why `end` requires `--run <path>`
rather than guessing at the newest unfinished record of the same Skill: guessing
would close a genuinely dead run from a previous session and erase its signal.

`end` is the one read-modify-write in this file, which Issue #750 avoided on
purpose. It is safe here for a reason that does not generalize: a run record has
no body and no comments (see below), so a YAML round-trip has nothing to lose —
unlike `config.yml`, where exactly that cost a file's worth of commented
examples (Issue #713).

## The body is always empty

Every other `.md` record here carries something in its body that frontmatter
cannot hold: `## Summary`, `## Failure Reason`, a reviewer's prose. A run record
is scalars and lists all the way down. JSON was the obvious alternative and was
not taken — matching the shape of the other records is worth more than saving
the delimiters. **The body stays empty**; it is not an invitation to write
something because there is room.

What is deliberately not recorded: cost and token counts (Issue #784 removed
billing figures from a distributed file for the same reason), page text or model
output (the page and its management file already hold it), individual judgments
(`## Summary` and `.wikicommit/review/` own those — this file holds the outward
shape of a run only), and per-script timings (most of the time is LLM inference
outside any script, so timing the cheap deterministic parts would measure the
wrong thing).

## Checkpoints say *where* a run got to (Issue #797)

`ended_at` answers whether a run finished. It says nothing about what happened
inside it, and two questions live in that gap:

- **Where did it stop?** The two halt paths change no file (guard C in Issue
  #574, a `rules_version` mismatch in Issue #752), so the run record is the only
  trace — and without a checkpoint that trace has no position.
- **Was a pass skipped?** Issues #406, #452 and #474 are all one class: a step at
  the tail of a long multi-pass flow silently does not run. All three were found
  by a human auditing a published pilot repository afterwards. All three were
  fixed by delegating the step to a deterministic script — which does nothing
  when the instruction to *call* that script is itself the step that drops.

`checkpoint` stamps the entry to each pass into the `passes` list. A missing
stamp is a pass that did not run; the last stamp is how far the run got.

**The verification has a third party.** Issue #752 could check that a subagent
had read the rules file because the subagent returns JSON an orchestrator
compares — and that same Issue records the limit: `wikicommit-review` uses no
subagent, so nothing checks it there. A single agent asserting it read a file,
to itself, verifies nothing. Handing the comparison to *this script* restores
the second party without needing a second agent: `--token` makes it open the
pass file on disk and compare, so the claim is checked against the file rather
than against the claim.

What that does and does not catch: a pass skipped entirely, and where a run
stopped, are both caught. A pass file opened and then disregarded is not — the
same limit `rules_version` has, since grepping one line out of a file is always
possible. The stamps stay in frontmatter as a list of flat mappings: the body
stays empty (see above), and "scalars and lists all the way down" still holds.

`check_run_records.py` is the consumer, without which this would be a receptacle
nothing reads — the shape Issue #553 rules out.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from _version import get_version  # noqa: E402

RUN_DIR = Path(".wikicommit/run")

# The Skills that write a record. The criterion is "if this dies partway, a
# half-finished state becomes indistinguishable from work that has not come up
# yet". `fix` and `remove` are single small edits whose diff is the result;
# `collect` is interactive with a human watching; the read-only Skills change no
# state, so asking whether they finished means nothing.
SKILLS = (
    "wikicommit-generate",
    "wikicommit-translate",
    "wikicommit-synthesize",
    "wikicommit-merge",
)

# Keep the newest N records and drop the rest at write time. A record is a few
# hundred bytes, so a count is enough and needs no clock (Issue #790).
KEEP_RECORDS = 50

# The passes a Skill stamps, in order (Issue #797). Only `wikicommit-generate`
# has one: it is the multi-pass Skill, and starting with it alone is how the
# shape gets confirmed before the other three inherit it. `merge`'s Step 1-10
# already leave their result in `end`'s `--outcome`.
#
# Pass 2a is deliberately not a checkpoint. It runs unconditionally, in the same
# breath as Pass 1's extraction, and has no branch and no halt of its own; the
# first place the flow inside Pass 2 can diverge is 2b's type-approval, which
# takes a different route under interactive and non-interactive runs. Adding a
# stamp there would cost a read-modify-write per source and locate nothing that
# Pass 1's stamp does not already locate.
EXPECTED_PASSES = {
    "wikicommit-generate": (
        "pass1-extract",
        "pass2b-type",
        "pass2c-entities",
        "pass3-generate",
        "pass4-review",
    ),
}

# `--regenerate` runs a narrower flow: it takes a page rather than a source, so
# the entities are already settled and Pass 2 does not run at all (Issue #578).
# Reporting 2b and 2c as missing there would be reporting the mode working as
# designed.
REGENERATE_PASSES = {
    "wikicommit-generate": ("pass1-extract", "pass3-generate", "pass4-review"),
}

# Where `--token` looks for the file whose token it is checking. The convention
# is fixed rather than configurable: the point of the check is that the script
# resolves the location itself, and a caller that could also name the file could
# name one it had just written.
PASS_FILE_DIR = "passes"

# What the `token:` field on a stamp can say. `unchecked` is what a caller that
# passed no `--token` gets — written rather than omitted so every stamp has the
# same shape, and so "nobody checked" is visibly different from "checked and
# fine" for a reader scanning the list.
TOKEN_UNCHECKED = "unchecked"
TOKEN_OK = "ok"
TOKEN_MISSING = "missing"
TOKEN_MISMATCH = "mismatch"

_STAMP_RE = re.compile(r"^\d{8}-\d{6}-")


class RunError(Exception):
    """A usage or filesystem problem worth reporting on stderr."""


def _slug(skill: str) -> str:
    """`wikicommit-generate` -> `generate`, for a readable filename."""
    return skill.removeprefix("wikicommit-") or skill


def run_sort_key(path: Path) -> tuple[str, int]:
    """Order records chronologically.

    The name is `<YYYYMMDD>-<HHMMSS>-<skill>[-<n>].md` and both time components
    are zero-padded and fixed-width, so plain lexical order over the name would
    be chronological — except for the collision suffix, since `-` precedes `.`
    and `...-generate-2.md` therefore sorts *before* `...-generate.md`. Reading
    the last filename would then pick the oldest record of that second, and
    rotation would prune the newest ones first.

    Writer and reader share this key, exactly as `record_review.py` has them
    share `record_sort_key()` for the same reason. An unexpected name (a
    hand-written file) sorts on its own name and stays visible rather than
    silently reordering the real records.
    """
    stem = path.stem
    parts = stem.split("-")
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
        seq = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1
        return (f"{parts[0]}-{parts[1]}", seq)
    return (stem, 0)


def allocate_run_path(directory: Path, stamp: str, skill: str) -> Path:
    """`<YYYYMMDD>-<HHMMSS>-<skill>.md`, suffixed on collision.

    Two runs starting in the same second is not something this can produce in
    practice, but overwriting a record is not a thing this file is allowed to do.
    """
    base = f"{stamp}-{_slug(skill)}"
    path = directory / f"{base}.md"
    n = 2
    while path.exists():
        path = directory / f"{base}-{n}.md"
        n += 1
    return path


def rotate(directory: Path, keep: int = KEEP_RECORDS) -> list[Path]:
    """Delete all but the newest `keep` records.

    Ordering goes through `run_sort_key()` rather than the bare filename, so a
    same-second collision suffix cannot make the newest record of that second
    look like the oldest and be pruned first.
    Unfinished records are not exempt: bounding the directory is the point, and
    a run old enough to fall off the end has stopped being actionable.
    """
    if keep <= 0:
        return []
    records = sorted(
        (p for p in directory.glob("*.md") if _STAMP_RE.match(p.name)),
        key=run_sort_key,
    )
    removed = []
    for path in records[:-keep] if len(records) > keep else []:
        try:
            path.unlink()
            removed.append(path)
        except OSError:
            # Rotation is housekeeping; failing to prune must never take down
            # the run whose start it is attached to.
            pass
    return removed


def write_record(path: Path, record: dict) -> None:
    front = yaml.safe_dump(record, sort_keys=False, allow_unicode=True, default_flow_style=False)
    path.write_text(f"---\n{front}---\n", encoding="utf-8")


def read_record(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise RunError(f"{path}: not a run record (no frontmatter)")
    _, _, rest = text.partition("---\n")
    front, sep, _ = rest.partition("\n---")
    if not sep:
        raise RunError(f"{path}: frontmatter is not terminated")
    try:
        data = yaml.safe_load(front)
    except yaml.YAMLError as e:
        raise RunError(f"{path}: frontmatter does not parse: {e}") from e
    if not isinstance(data, dict):
        raise RunError(f"{path}: frontmatter is not a mapping")
    return data


def parse_outcome(pairs: list[str]) -> dict[str, int]:
    """`generated=12` pairs into a mapping.

    The keys are left to the caller rather than fixed here: `merge` counts
    something other than pages, and inventing one shared vocabulary for both
    would mean shipping keys that are permanently zero for one of them.
    """
    outcome: dict[str, int] = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key = key.strip()
        if not sep or not key:
            raise RunError(f"--outcome expects KEY=VALUE, got: {pair}")
        try:
            outcome[key] = int(value)
        except ValueError as e:
            raise RunError(f"--outcome {key} expects an integer, got: {value!r}") from e
    return outcome


def format_elapsed(start: datetime, end: datetime) -> str:
    if (start.tzinfo is None) != (end.tzinfo is None):
        # A record is always written with an aware stamp, but this tree is not
        # tracked and is meant to be readable by hand, so one of the two can end
        # up naive. Subtracting a naive from an aware datetime raises TypeError,
        # which would take down a run that had already finished and — in
        # `check_run_records.py` — the `INCOMPLETE_RUN:` list along with it.
        return "unknown"
    seconds = int((end - start).total_seconds())
    if seconds < 0:
        return "unknown"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{seconds:02d}s"
    return f"{seconds}s"


def expected_passes(record: dict) -> tuple[str, ...]:
    """The passes this run was supposed to stamp, in order.

    Narrowed for `--regenerate`, which skips Pass 2 entirely by design. Reading
    that off the record's own `args` keeps the narrowing where the fact lives
    instead of asking the caller to restate it at checkpoint time.
    """
    skill = str(record.get("skill") or "")
    args = record.get("args")
    args = args if isinstance(args, list) else []
    if any(str(a).startswith("--regenerate") for a in args) and skill in REGENERATE_PASSES:
        return REGENERATE_PASSES[skill]
    return EXPECTED_PASSES.get(skill, ())


def pass_file_for(skill: str, pass_name: str) -> Path:
    """`.claude/skills/<skill>/passes/<pass>.md` — the file `--token` reads."""
    return Path(".claude/skills") / skill / PASS_FILE_DIR / f"{pass_name}.md"


def read_pass_token(path: Path) -> str | None:
    """The `pass_token` declared in a pass file's frontmatter, or None.

    None covers every way the file can fail to yield one — absent, unparseable,
    no such key. The caller treats all of them the same way, because they are
    the same thing from the checkpoint's point of view: nothing on disk backs
    the token that was just claimed.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---\n")
    front, sep, _ = rest.partition("\n---")
    if not sep:
        return None
    try:
        data = yaml.safe_load(front)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    token = data.get("pass_token")
    return str(token) if token not in (None, "") else None


def cmd_checkpoint(args) -> int:
    """Stamp the entry to one pass onto an open run record (Issue #797)."""
    path = Path(args.run)
    if not path.is_file():
        raise RunError(f"{args.run}: no such run record (pass the path `start` printed)")
    record = read_record(path)

    skill = str(record.get("skill") or "")
    known = EXPECTED_PASSES.get(skill, ())
    if known and args.pass_name not in known:
        # A typo would otherwise land as an unknown pass *and* leave the real one
        # looking as though it never ran — one slip reported as two failures, and
        # neither of them the actual one.
        raise RunError(
            f"--pass {args.pass_name!r} is not a pass of {skill} "
            f"(expected one of: {', '.join(known)})"
        )

    token_state = TOKEN_UNCHECKED
    failure = ""
    if args.token:
        pass_file = pass_file_for(skill, args.pass_name)
        declared = read_pass_token(pass_file)
        if declared is None:
            token_state = TOKEN_MISSING
            failure = (
                f"{pass_file}: no pass_token to check --token against "
                "(the file is absent, unreadable, or declares none)"
            )
        elif declared != args.token:
            token_state = TOKEN_MISMATCH
            failure = (
                f"{pass_file}: pass_token does not match --token "
                "(this pass ran without its file being read)"
            )
        else:
            token_state = TOKEN_OK

    stamp = {
        "pass": args.pass_name,
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "token": token_state,
    }
    if args.source:
        # The unit the pass is iterating over: a source management file normally,
        # the page being rebuilt under `--regenerate`. Without it a run that died
        # on its third source is indistinguishable from one that died on its
        # first, since the pass names repeat once per source.
        stamp["source"] = args.source
    passes = record.get("passes")
    record["passes"] = ([*passes] if isinstance(passes, list) else []) + [stamp]
    # The stamp is written even when the token check failed. A checkpoint that
    # refused to record its own failure would leave the run looking as though the
    # pass never started, which is a different — and wrong — story.
    write_record(path, record)

    suffix = f", source={args.source}" if args.source else ""
    print(f"CHECKPOINT: {path} (pass={args.pass_name}, token={token_state}{suffix})")
    if failure:
        print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


def cmd_start(args) -> int:
    directory = RUN_DIR
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    record = {
        "skill": args.skill,
        "started_at": now.isoformat(timespec="seconds"),
        # Written empty rather than omitted so the record says, in the same
        # shape it will hold a real timestamp, that this run has not finished.
        "ended_at": "",
        "model": args.model,
        "wikicommit_version": get_version(),
        "args": list(args.args),
        "sources": [],
        "pages": [],
        # Empty rather than absent, in the same shape the stamps will take: a run
        # that recorded nothing is then visibly different from one written before
        # checkpoints existed, whose records have no such key at all (Issue #797).
        "passes": [],
        "outcome": {},
        "halted_reason": "",
    }
    path = allocate_run_path(directory, now.strftime("%Y%m%d-%H%M%S"), args.skill)
    write_record(path, record)
    rotate(directory)
    print(f"RUN_STARTED: {path} (skill={args.skill}, started_at={record['started_at']})")
    print("NOTE: pass this path back to `record_run.py end` when the run finishes.")
    return 0


def cmd_end(args) -> int:
    path = Path(args.run)
    if not path.is_file():
        raise RunError(f"{args.run}: no such run record (pass the path `start` printed)")
    record = read_record(path)
    now = datetime.now().astimezone()
    record["ended_at"] = now.isoformat(timespec="seconds")
    if args.sources:
        record["sources"] = list(args.sources)
    if args.pages:
        record["pages"] = list(args.pages)
    if args.outcome:
        record["outcome"] = parse_outcome(args.outcome)
    if args.halted_reason:
        record["halted_reason"] = args.halted_reason
    write_record(path, record)

    started = str(record.get("started_at") or "")
    elapsed = ""
    if started:
        try:
            elapsed = f", elapsed={format_elapsed(datetime.fromisoformat(started), now)}"
        except (ValueError, TypeError):
            elapsed = ""
    print(f"RUN_ENDED: {path} (ended_at={record['ended_at']}{elapsed})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record one run of a Skill, keyed on the run rather than its output (Issue #790)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="open a record; leaves ended_at empty")
    start.add_argument("--skill", required=True, choices=SKILLS)
    start.add_argument("--model", default="", help="runtime-reported model ID")
    start.add_argument("--arg", dest="args", action="append", default=[], metavar="ARG",
                       help="an argument this run was invoked with (repeatable)")

    check = sub.add_parser("checkpoint", help="stamp the entry to one pass (Issue #797)")
    check.add_argument("run", help="path printed by `start`")
    check.add_argument("--pass", dest="pass_name", required=True, metavar="NAME",
                       help="the pass being entered, e.g. pass1-extract")
    check.add_argument("--token", default="", metavar="TOKEN",
                       help="pass_token claimed for this pass; checked against the pass file on disk")
    check.add_argument("--source", default="", metavar="PATH",
                       help="the source (or, under --regenerate, the page) this pass is running for")

    end = sub.add_parser("end", help="close the record opened by `start`")
    end.add_argument("run", help="path printed by `start`")
    end.add_argument("--source", dest="sources", action="append", default=[], metavar="PATH")
    end.add_argument("--page", dest="pages", action="append", default=[], metavar="PATH")
    end.add_argument("--outcome", action="append", default=[], metavar="KEY=VALUE")
    end.add_argument("--halted-reason", default="",
                     help="why the run stopped without changing any file")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"start": cmd_start, "checkpoint": cmd_checkpoint, "end": cmd_end}
    try:
        return handlers[args.command](args)
    except (RunError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
