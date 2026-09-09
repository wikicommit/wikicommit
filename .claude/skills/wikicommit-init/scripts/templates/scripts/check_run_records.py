#!/usr/bin/env python3
"""check_run_records.py — read the run records back (Issue #790).

`record_run.py` writes one immutable-until-closed file per run under
`.wikicommit/run/`. This is the consumer that makes that tree worth having;
without it the records would be a receptacle nothing reads, which is the shape
Issue #553 rules out.

Three lines, answering the questions the run records exist for:

- `LAST_RUN:` — when the last run of any Skill happened, how long it took, and
  what it produced. This is the only place either "when" or "how long" is
  available: `generated_at` is a date, a commit timestamp is the merge, and no
  layer has ever held a duration at all.
- `INCOMPLETE_RUN:` — a record with a start and no end. That is a run that did
  not finish, and the state it leaves behind is otherwise indistinguishable from
  a backlog that has simply not come up yet (Issue #567) — or, on the two halt
  paths that stop everything before any file changes (guard C in Issue #574, a
  `rules_version` mismatch in Issue #752), from nothing having been run at all.
  When the run recorded why it stopped, `halted_reason` is on the line, and when
  it stamped checkpoints, so is how far it got.
- `MISSING_PASS:` — a run that *did* finish, with a pass that left no stamp. That
  is the shape of Issues #406, #452 and #474, all three of which were a step at
  the tail of a long flow silently not running, and all three of which a human
  found afterwards by auditing a published repository (Issue #797).

**`MISSING_PASS:` is an observation, not a verdict** — the posture
`check_installed_type_usage.py` takes with `ANCESTOR_FALLBACK:`. A run can
legitimately end without reaching every pass: every source blocked at Pass 1 or
already up to date leaves nothing for Pass 2 onward to do. What the line reports
is that the run finished having skipped something, which is worth a look and is
not on its own a defect.

Records written before checkpoints existed carry no `passes` key at all, and
nothing about passes is printed for them. That is the difference between "no
stamps" and "an empty list of stamps", and it is why `start` writes the key
empty rather than leaving it out.

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

from record_run import (  # noqa: E402
    RUN_DIR,
    _STAMP_RE,
    expected_passes,
    format_elapsed,
    read_record,
    run_sort_key,
)


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


def stamped_passes(record: dict) -> list[str]:
    """The pass names this run stamped, in the order it stamped them.

    Repeats are kept: `wikicommit-generate` walks the passes once per source, so
    the same name appearing five times is five sources, not a duplicate.
    """
    passes = record.get("passes")
    if not isinstance(passes, list):
        return []
    names = []
    for entry in passes:
        if isinstance(entry, dict) and entry.get("pass"):
            names.append(str(entry["pass"]))
    return names


def has_checkpoints(record: dict) -> bool:
    """Whether this record is from a run that stamped checkpoints at all.

    A record written before Issue #797 has no `passes` key; one written after it
    by a Skill that stamps nothing has an empty list. Neither can be reported on,
    and saying nothing is the only honest output for both.
    """
    return bool(stamped_passes(record))


def missing_passes(record: dict) -> list[str]:
    """Expected passes with no stamp, in the expected order."""
    stamped = set(stamped_passes(record))
    return [name for name in expected_passes(record) if name not in stamped]


def _pass_detail(record: dict) -> str:
    """`reached X; Y, Z never ran` — where the run got to, and what it skipped."""
    if not has_checkpoints(record):
        return ""
    parts = [f"reached {stamped_passes(record)[-1]}"]
    missing = missing_passes(record)
    if missing:
        parts.append(f"{', '.join(missing)} never ran")
    return "; ".join(parts)


def describe_last(record: dict) -> str:
    count = len(stamped_passes(record))
    passes = f"{count} pass(es)" if count else ""
    parts = [p for p in (_elapsed(record), passes, _outcome(record)) if p]
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"{_when(record)} {record.get('skill') or 'unknown'}{detail}"


def describe_incomplete(record: dict) -> str:
    reason = str(record.get("halted_reason") or "").strip()
    # "no ended_at" is the literal state of the record; the reason, when the run
    # managed to record one, says why; the checkpoints say where it got to.
    # Three different facts, and all three fit on the line.
    detail = f"no ended_at — halted: {reason}" if reason else "no ended_at"
    position = _pass_detail(record)
    if position:
        detail = f"{detail} — {position}"
    return f"{_when(record)} {record.get('skill') or 'unknown'} ({detail})"


def describe_missing_pass(record: dict) -> str:
    return (
        f"{_when(record)} {record.get('skill') or 'unknown'} "
        f"(finished, but {', '.join(missing_passes(record))} left no stamp)"
    )


def main() -> int:
    if not RUN_DIR.exists():
        # Distinguish "nothing has been run since records existed" from "every
        # run finished": only the first means there was nothing to look at.
        print("SUMMARY: runs=0, incomplete=0, missing_pass=0")
        print(f"NOTE: {RUN_DIR.as_posix()}/ does not exist yet; no runs have been recorded.")
        return 0

    records = load_records(RUN_DIR)
    if not records:
        print("SUMMARY: runs=0, incomplete=0, missing_pass=0")
        print(f"NOTE: {RUN_DIR.as_posix()}/ holds no run records yet.")
        return 0

    incomplete = [(p, r) for p, r in records if not str(r.get("ended_at") or "").strip()]
    # A finished run only. An unfinished one is already reported above, and it has
    # an obvious reason for the gap — reporting it twice would say the same thing
    # in two voices, one of which ("finished, but") would be false.
    skipped = [
        (p, r)
        for p, r in records
        if str(r.get("ended_at") or "").strip() and has_checkpoints(r) and missing_passes(r)
    ]

    print(f"LAST_RUN: {describe_last(records[-1][1])}")
    for _, record in incomplete:
        print(f"INCOMPLETE_RUN: {describe_incomplete(record)}")
    for _, record in skipped:
        print(f"MISSING_PASS: {describe_missing_pass(record)}")
    print(
        f"SUMMARY: runs={len(records)}, incomplete={len(incomplete)}, "
        f"missing_pass={len(skipped)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
