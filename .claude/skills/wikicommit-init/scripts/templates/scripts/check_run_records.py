#!/usr/bin/env python3
"""check_run_records.py — read the run records back (Issue #790).

`record_run.py` writes one immutable-until-closed file per run under
`.wikicommit/run/`. This is the consumer that makes that tree worth having;
without it the records would be a receptacle nothing reads, which is the shape
Issue #553 rules out.

Two lines, answering the two questions the run records exist for:

- `LAST_RUN:` — when the last run of any Skill happened, how long it took, and
  what it produced. This is the only place either "when" or "how long" is
  available: `generated_at` is a date, a commit timestamp is the merge, and no
  layer has ever held a duration at all.
- `INCOMPLETE_RUN:` — a record with a start and no end. That is a run that did
  not finish, and the state it leaves behind is otherwise indistinguishable from
  a backlog that has simply not come up yet (Issue #567) — or, on the two halt
  paths that stop everything before any file changes (guard C in Issue #574, a
  `rules_version` mismatch in Issue #752), from nothing having been run at all.
  When the run recorded why it stopped, `halted_reason` is on the line.

**A forgotten closing stamp reports here too**, and that is the accepted
direction of the error rather than a defect: a completed run shown as incomplete
costs a glance, while the reverse would quietly retire the question. See
`record_run.py` for why `end` will not guess at which record to close.

Only one `LAST_RUN:` is printed. The question it answers is "did the thing I
just ran get anywhere", which is about the last run and not a history — and the
history is bounded by rotation anyway, so a longer list would report an
arbitrary window rather than a complete one. Every incomplete record is listed:
those are individually actionable, and rotation already bounds how many there
can be.

This reads only. It never deletes a record, never closes one, and never writes
anything — rotation belongs to the writer, at the moment a new record is opened.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from record_run import RUN_DIR, _STAMP_RE, format_elapsed, read_record, run_sort_key  # noqa: E402


def load_records(directory: Path) -> list[tuple[Path, dict]]:
    """Every parseable record, oldest first.

    Ordering goes through `record_run.run_sort_key()` rather than the bare
    filename: a same-second collision suffix sorts before the unsuffixed name,
    so taking the last entry as `LAST_RUN:` would report the oldest record of
    that second. Writer and reader share the key.
    """
    records = []
    for path in sorted(directory.glob("*.md"), key=run_sort_key):
        if not _STAMP_RE.match(path.name):
            continue
        try:
            records.append((path, read_record(path)))
        except Exception as e:
            # A record that cannot be read is worth saying out loud rather than
            # dropping: silently skipping it would understate the incomplete
            # count, which is the one number here that has to err high.
            print(f"WARNING: {path}: could not be read: {e}", file=sys.stderr)
    return records


def _when(record: dict) -> str:
    started = str(record.get("started_at") or "")
    try:
        return datetime.fromisoformat(started).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return started or "unknown"


def _elapsed(record: dict) -> str:
    started, ended = str(record.get("started_at") or ""), str(record.get("ended_at") or "")
    if not started or not ended:
        return ""
    try:
        return format_elapsed(datetime.fromisoformat(started), datetime.fromisoformat(ended))
    except (ValueError, TypeError):
        # A hand-edited stamp can be unparseable, or naive where the other is
        # aware. Neither may cost the caller `LAST_RUN:` and the whole
        # `INCOMPLETE_RUN:` list, which is the number that has to err high.
        return ""


def _outcome(record: dict) -> str:
    outcome = record.get("outcome")
    if not isinstance(outcome, dict) or not outcome:
        return ""
    return " ".join(f"{k}={v}" for k, v in outcome.items())


def describe_last(record: dict) -> str:
    parts = [p for p in (_elapsed(record), _outcome(record)) if p]
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"{_when(record)} {record.get('skill') or 'unknown'}{detail}"


def describe_incomplete(record: dict) -> str:
    reason = str(record.get("halted_reason") or "").strip()
    # "no ended_at" is the literal state of the record; the reason, when the run
    # managed to record one, says why — those are different facts and both fit.
    detail = f"no ended_at — halted: {reason}" if reason else "no ended_at"
    return f"{_when(record)} {record.get('skill') or 'unknown'} ({detail})"


def main() -> int:
    if not RUN_DIR.exists():
        # Distinguish "nothing has been run since records existed" from "every
        # run finished": only the first means there was nothing to look at.
        print("SUMMARY: runs=0, incomplete=0")
        print(f"NOTE: {RUN_DIR.as_posix()}/ does not exist yet; no runs have been recorded.")
        return 0

    records = load_records(RUN_DIR)
    if not records:
        print("SUMMARY: runs=0, incomplete=0")
        print(f"NOTE: {RUN_DIR.as_posix()}/ holds no run records yet.")
        return 0

    incomplete = [(p, r) for p, r in records if not str(r.get("ended_at") or "").strip()]

    print(f"LAST_RUN: {describe_last(records[-1][1])}")
    for _, record in incomplete:
        print(f"INCOMPLETE_RUN: {describe_incomplete(record)}")
    print(f"SUMMARY: runs={len(records)}, incomplete={len(incomplete)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
