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
- `INCOMPLETE_RUN:` — a run that did not finish **normally**: either a record
  with a start and no end, or one closed by a halt. The state either leaves
  behind is otherwise indistinguishable from a backlog that has simply not come
  up yet (Issue #567) — or, on the two halt paths that stop everything before any
  file changes (guard C in Issue #574, a `rules_version` mismatch in Issue #752),
  from nothing having been run at all. When the run recorded why it stopped,
  `halted_reason` is on the line, and when it stamped checkpoints, so is how far
  it got. Halts used to land on the finished side, because `ended_at` was
  standing in for "finished" and `end --halted-reason` writes one; see
  `finished_normally()` (Issue #872).
- `MISSING_PASS:` — a run that finished **normally**, with a pass that left no
  stamp. That is the shape of Issues #406, #452 and #474, all three of which
  were a step at the tail of a long flow silently not running, and all three of
  which a human found afterwards by auditing a published repository (Issue #797).

**`MISSING_PASS:` is an observation, not a verdict** — the posture
`check_installed_type_usage.py` takes with `ANCESTOR_FALLBACK:`. A run can
legitimately end without reaching every pass: every source blocked at Pass 1 or
already up to date leaves nothing for Pass 2 onward to do. What the line reports
is that the run finished having skipped something, which is worth a look and is
not on its own a defect.

Records written before checkpoints existed carry no `passes` key at all, and
nothing about passes is printed for them. **An empty list is a different thing**
and is reported (Issue #864): `start` writes the key empty rather than leaving it
out, so a run that stamped nothing is distinguishable from one that could not
have, and the first of those is the worst case this line exists for — every
stamping instruction lost rather than one. Reporting only the partial case had
the line fall silent exactly where the failure was total.

A zero-stamp run is reported only when the record shows it did work — a source or
page it named, or a non-zero outcome count. Without that gate the line would be
on for most runs: a bare `/wikicommit-generate` on an up-to-date wiki finds
nothing to process and finishes with no stamp, legitimately and usually.

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
    """Whether this record carries at least one stamp.

    This is the question `_pass_detail()` needs — "how far did it get" has no
    answer without a last stamp to name — and it also picks which of the two
    `MISSING_PASS:` line shapes applies.

    It is *not* the gate on whether a record can be reported at all; that is
    `records_passes()`, which keys on the `passes` key rather than on the stamps.
    But it **is** one half of the report gate in `main()`: a run with at least one
    stamp is reported whether or not it recorded any work, which is what keeps
    `work_recorded()`'s suppression confined to the zero-stamp case it was added
    for. Dropping this clause would silently retire the one gap the zero-stamp
    rule leaves open: a run whose closing call lost its `--source` / `--page` /
    `--outcome` flags to the same compaction that dropped its later stamps still
    holds the stamps it managed before that, and those are all that keep it
    reportable. The guard C halt used to be the example here; since Issue #872 it
    carries a `halted_reason`, so it is not `finished_normally` and never reaches
    this gate at all — it is reported on `INCOMPLETE_RUN:` instead.
    """
    return bool(stamped_passes(record))


def records_passes(record: dict) -> bool:
    """Whether this record is from a run that could have stamped at all.

    A record written before Issue #797 has no `passes` key, and nothing about
    passes can honestly be said of it. One written after it carries the key — an
    empty list when the run stamped nothing — and `record_run.py`'s `start`
    writes it empty rather than leaving it out precisely so the two are
    distinguishable (Issue #864). Keying the gate on the key rather than on the
    stamps is what lets the worst case be reported: a run that lost *every*
    stamping instruction to compaction leaves `passes: []`, and treating that as
    "predates stamping" hid exactly the case these stamps exist for.
    """
    return isinstance(record.get("passes"), list)


def work_recorded(record: dict) -> bool:
    """Whether the record shows the run actually did something.

    This is the gate that keeps the widening above from lighting up on the common
    case. A bare `/wikicommit-generate` on an up-to-date wiki finds no management
    file to process and says so and exits (Pass 1 step 2) — a legitimate finish
    with no stamp at all, and on a wiki that is current it is the *usual* finish.
    Reporting it would put this line on most runs, and a line that is always on
    stops being read (the force Issue #562 weighed when it demoted the
    low-density guard).

    So a zero-stamp run is only reported when the record itself shows work: a
    source or page it named, or an outcome count that is not zero. A run that
    halted before Pass 1 likewise recorded none of those, so it falls out here
    without needing a rule of its own.

    Non-integer outcome values count as work: a hand-edited record should not be
    read as having done nothing because its value cannot be parsed.
    """
    if record.get("sources") or record.get("pages"):
        return True
    outcome = record.get("outcome")
    if not isinstance(outcome, dict):
        return bool(outcome)
    return any(value not in (0, "0", "", None, False) for value in outcome.values())


def finished_normally(record: dict) -> bool:
    """Whether the run finished normally — closed, and not halted.

    **`ended_at` is not that question.** It was standing in for it, and the halt
    paths broke the proxy: guard C (Issue #574) and a `rules_version` mismatch
    (Issue #752) both stop everything and close the record through
    `record_run.py end --halted-reason`, so they carry an `ended_at` and landed
    on the finished side. That put them under `MISSING_PASS:` saying
    "finished, but ... left no stamp" — false on both halves, since a halt did
    not finish and not reaching the later passes is the point rather than an
    omission (Issue #872).

    Deriving both `INCOMPLETE_RUN:` and `MISSING_PASS:` from this one predicate
    is what makes the second half fall out for free: a halt is not
    `finished_normally`, so it leaves the skipped list without a rule of its own.

    It also reaches the halts `MISSING_PASS:` never could. `EXPECTED_PASSES`
    holds one entry (`wikicommit-generate`), so for `wikicommit-synthesize` /
    `wikicommit-translate` / `wikicommit-merge` the expected set is empty, the
    missing set with it, and no fix to that line could have surfaced their halts
    at all. `halted_reason` is on every record — `start` writes it empty — so
    judging on it covers every Skill.

    The cost is that "forgot to stamp the close" and "halted" are now told apart
    by `halted_reason` alone. That was always the only value separating them,
    and it is on the line.
    """
    ended = str(record.get("ended_at") or "").strip()
    halted = str(record.get("halted_reason") or "").strip()
    return bool(ended) and not halted


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
    """The most recent run: when, which Skill, how long, and what it produced.

    A halt is named here too. Only one `LAST_RUN:` is printed, so when the halt
    is the most recent run this is the only line it can appear on besides
    `INCOMPLETE_RUN:` — and without the word, a halt reads as an ordinary run
    that happened to take five minutes (Issue #872).
    """
    count = len(stamped_passes(record))
    passes = f"{count} pass(es)" if count else ""
    reason = str(record.get("halted_reason") or "").strip()
    halted = f"halted: {reason}" if reason else ""
    parts = [p for p in (halted, _elapsed(record), passes, _outcome(record)) if p]
    detail = f" ({', '.join(parts)})" if parts else ""
    return f"{_when(record)} {record.get('skill') or 'unknown'}{detail}"


def describe_incomplete(record: dict) -> str:
    """Why this run did not finish normally, and how far it got.

    Two shapes, because the two ways of not finishing leave different records.
    A run that was never closed has no `ended_at`, and saying so is the literal
    state of the file. A halt **did** close its record, so "no ended_at" would be
    false there; what it has instead is a reason and an elapsed time, and the
    elapsed time is the whole reason `end --halted-reason` keeps writing
    `ended_at` (Issue #872) — guard C halts before fetching anything while a
    `rules_version` mismatch halts after reaching Pass 4, and those differ by
    orders of magnitude. The checkpoints say where it got to in either shape.
    """
    reason = str(record.get("halted_reason") or "").strip()
    ended = str(record.get("ended_at") or "").strip()
    if reason:
        elapsed = _elapsed(record)
        detail = f"halted: {reason}" + (f" ({elapsed})" if elapsed else "")
        if not ended:
            # Both at once: halted and never closed. Say both — the record is
            # hand-editable, and dropping either would describe it wrongly.
            detail = f"no ended_at — {detail}"
    else:
        detail = "no ended_at"
    position = _pass_detail(record)
    if position:
        detail = f"{detail} — {position}"
    return f"{_when(record)} {record.get('skill') or 'unknown'} ({detail})"


def _work_summary(record: dict) -> str:
    """`3 source(s), 12 page(s), generated=12` — the evidence the run did work.

    Printed only on the zero-stamp line, where it is the reason the line is being
    printed at all rather than suppressed as a no-op run. It therefore has to be
    able to name **every** shape `work_recorded()` accepts, including the loose
    ones a hand-edited record can hold: counting only well-formed lists and
    mappings would print the strongest finding this line produces with no stated
    basis at all, which is the one thing this summary exists to supply.
    """
    parts = []
    for key, noun in (("sources", "source"), ("pages", "page")):
        value = record.get(key)
        if isinstance(value, list) and value:
            parts.append(f"{len(value)} {noun}(s)")
        elif value:
            # A bare scalar where a list belongs. There is no count to give, so
            # say that an entry is there rather than dropping it silently.
            parts.append(f"a {noun} entry")
    outcome = _outcome(record)
    if outcome:
        parts.append(outcome)
    elif record.get("outcome"):
        # Truthy but not a mapping, so `_outcome()` cannot format it — same case
        # as above, and `work_recorded()` counted it.
        parts.append("an outcome entry")
    return ", ".join(parts)


def describe_missing_pass(record: dict) -> str:
    missing = ", ".join(missing_passes(record))
    if has_checkpoints(record):
        return f"{_when(record)} {record.get('skill') or 'unknown'} (finished, but {missing} left no stamp)"
    # Zero stamps is the worst case, not a milder one: every stamping instruction
    # went missing rather than one. Say that rather than listing five passes as
    # though they had been skipped one at a time, and name the work the record
    # holds — that is what separates this from a run that had nothing to do.
    work = _work_summary(record)
    evidence = f" — the record holds {work}" if work else ""
    return (
        f"{_when(record)} {record.get('skill') or 'unknown'} "
        f"(finished but stamped no pass at all{evidence}; {missing} never ran)"
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

    incomplete = [(p, r) for p, r in records if not finished_normally(r)]
    # A run that finished normally only. One that did not is already reported
    # above, and it has an obvious reason for the gap — reporting it twice would
    # say the same thing in two voices, one of which ("finished, but") would be
    # false. Sharing the predicate is what keeps halts out of here without a
    # clause of their own (Issue #872).
    skipped = [
        (p, r)
        for p, r in records
        if finished_normally(r)
        and records_passes(r)
        and missing_passes(r)
        and (has_checkpoints(r) or work_recorded(r))
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
