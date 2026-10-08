#!/usr/bin/env python3
"""Measure, per workflow step, how much context a real Skill run used.

Issue #1267. `tools/report_workflow_context_cost.py` says how much instruction
text the engine *points at*; this says what a run actually *carried*. Two inputs:

- **Run records** (`.wikicommit/run/<run>.md`, one or more). The workflow engine
  logs every step it completes, skips or has answered under `workflow.log`, each
  entry with an `at` time; the record itself has `started_at`.
- **Claude Code conversation logs** (`~/.claude/projects/<project>/*.jsonl`, one
  or more). Every assistant message carries a `timestamp` and the API `usage`
  (`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`).

A log entry's `at` is when the step was *finished*, so the work of a step is
every API call after the previous entry's `at` and up to its own. The engine
writes `at` to the second (truncated), while the call that reports a step done
is logged a fraction of a second before the engine runs; calls are therefore
compared by the second they fall in, so that call stays with its own step. For each
step the tool prints the number of API calls, the context size at the end of the
step (input + cache creation + cache read of its last call), the growth over the
previous step, and the instruction-file reads that happened inside it — the
`Read` tool calls (and `cat`/`sed`/`head` in `Bash`, also after `cd … &&`) on
a `.md` under `.claude/skills/`, directly under `.wikicommit/` or under
`.wikicommit/schema/` (the type template a step reads per item, whose size
`report_workflow_context_cost.py` cannot know), with the size of what came
back. Counting those per file across the run answers whether a `for_each` loop
re-reads its instructions for every item, and whether a re-read cost anything
(a harness may return a short "unchanged" stub for the second read).

Context is the main conversation only: subagent messages (`isSidechain: true`,
or a log under `subagents/`) do not add to the parent's context and are counted
separately as `subagent calls`. A message the log splits over several lines
(one per content block, same `message.id`) is counted once.

**Nothing is sent anywhere, and nothing of a page or source is printed** — only
counts, sizes, step ids, item names (management-file paths) and the paths of the
instruction files read. Logs of agents other than Claude Code are not read (their
format differs).

Usage:
    python tools/measure_workflow_context.py --run .wikicommit/run/<a>.md [--run ...]
        --log ~/.claude/projects/<project>/<session>.jsonl [--log ...] [--json]

Exit code: 0, or 2 on a usage error / unreadable input.
Dev-only (not distributed).
"""

import argparse
import json
import re
import sys
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".wikicommit" / "scripts"))

import record_run  # noqa: E402
import skill_workflow  # noqa: E402

INSTRUCTION_PATH = re.compile(
    r"((?:[^\s'\"`]*/)?(?:\.claude/skills/[^\s'\"`]+|\.wikicommit/(?:schema/)?[^/\s'\"`]+)\.md)"
)
READING_COMMAND = re.compile(r"^\s*(?:cat|sed|head|tail|less|awk)\b")
# Separators between the commands of one shell line (`cd x && cat y.md | head`).
COMMAND_SEPARATOR = re.compile(r"&&|\|\||[;|\n]")


class MeasureError(Exception):
    pass


def parse_time(value) -> datetime:
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone(timezone.utc)


def short_path(path: str) -> str:
    """The path from `.claude/` or `.wikicommit/` on, so runs on two machines compare."""
    for marker in (".claude/skills/", ".wikicommit/"):
        index = path.find(marker)
        if index >= 0:
            return path[index:]
    return path


# --- run records ---------------------------------------------------------------


def read_run(path: Path) -> dict:
    try:
        record = record_run.read_record(path)
    except OSError as e:
        raise MeasureError(f"{path}: {e}") from e
    except record_run.RunError as e:
        raise MeasureError(str(e)) from e
    state = skill_workflow.run_state(record)
    if not isinstance(state, dict) or not isinstance(state.get("log"), list):
        raise MeasureError(f"{path}: no workflow log (the run was not opened by skill_workflow.py)")
    if not record.get("started_at"):
        raise MeasureError(f"{path}: no started_at")
    entries = []
    for entry in state["log"]:
        if isinstance(entry, dict) and entry.get("at"):
            entries.append({
                "step": str(entry.get("step", "")),
                "item": entry.get("item"),
                "result": entry.get("outcome") or entry.get("answer") or "",
                "at": parse_time(entry["at"]),
            })
    entries.sort(key=lambda e: e["at"])
    return {
        "path": path.as_posix(),
        "skill": str(record.get("skill", "")),
        "started_at": parse_time(record["started_at"]),
        "entries": entries,
    }


# --- conversation logs ---------------------------------------------------------


def _result_size(content) -> int:
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, list):
        size = 0
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                size += len(block["text"].encode("utf-8"))
        return size
    return 0


def _read_targets(block: dict) -> list[str]:
    name = block.get("name")
    data = block.get("input") or {}
    if name == "Read":
        path = str(data.get("file_path", "")).replace("\\", "/")
        found = INSTRUCTION_PATH.search(path)
        return [path] if found and found.end() == len(path) else []
    if name == "Bash":
        targets: list[str] = []
        for command in COMMAND_SEPARATOR.split(str(data.get("command", ""))):
            if READING_COMMAND.match(command):
                targets.extend(INSTRUCTION_PATH.findall(command))
        return targets
    return []


def read_logs(paths: list[Path]) -> tuple[list[dict], list[dict], int]:
    """(main-conversation calls, instruction reads, subagent calls) from the logs."""
    calls: dict[str, dict] = {}
    reads: dict[str, dict] = {}
    sizes: dict[str, int] = {}
    subagent_ids: set[str] = set()
    for path in paths:
        side_file = "subagents" in path.parts
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as e:
            raise MeasureError(f"{path}: {e}") from e
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                raise MeasureError(f"{path}:{number}: not JSON: {e}") from e
            message = row.get("message") if isinstance(row.get("message"), dict) else {}
            content = message.get("content") if isinstance(message.get("content"), list) else []
            if row.get("type") == "user":
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        sizes[str(block.get("tool_use_id"))] = _result_size(block.get("content"))
                continue
            if row.get("type") != "assistant" or not row.get("timestamp"):
                continue
            message_id = str(message.get("id") or row.get("uuid") or f"{path}:{number}")
            if side_file or row.get("isSidechain"):
                subagent_ids.add(message_id)
                continue
            usage = message.get("usage") or {}
            moment = parse_time(row["timestamp"])
            context = sum(int(usage.get(k) or 0) for k in (
                "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            output = int(usage.get("output_tokens") or 0)
            if message_id not in calls:
                calls[message_id] = {"at": moment, "context": context, "output": output}
            else:
                # the lines of one split message may carry streaming-time usage;
                # keep the largest figures seen for it
                known = calls[message_id]
                known["context"] = max(known["context"], context)
                known["output"] = max(known["output"], output)
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                for target in _read_targets(block):
                    key = f"{block.get('id')}|{target}"
                    reads.setdefault(key, {"at": moment, "file": short_path(target),
                                           "tool_use_id": str(block.get("id"))})
    for read in reads.values():
        read["bytes"] = sizes.get(read.pop("tool_use_id"))
    return (sorted(calls.values(), key=lambda c: c["at"]),
            sorted(reads.values(), key=lambda r: r["at"]),
            len(subagent_ids))


# --- matching ------------------------------------------------------------------


def _second(moment: datetime) -> datetime:
    """`moment` truncated to the second, the precision the engine writes `at` in."""
    return moment.replace(microsecond=0)


def measure(runs: list[dict], calls: list[dict], reads: list[dict]) -> list[dict]:
    call_seconds = [_second(c["at"]) for c in calls]
    read_seconds = [_second(r["at"]) for r in reads]
    reports = []
    for run in runs:
        steps = []
        previous_context = None
        # the context just before the run: the last call before it started
        first = bisect_right(call_seconds, run["started_at"])
        if first:
            previous_context = calls[first - 1]["context"]
        first_read = bisect_right(read_seconds, run["started_at"])
        start_context = previous_context
        for entry in run["entries"]:
            last = bisect_right(call_seconds, entry["at"])
            last_read = bisect_right(read_seconds, entry["at"])
            window = calls[first:last]
            step_reads = reads[first_read:last_read]
            first, first_read = max(first, last), max(first_read, last_read)
            end_context = window[-1]["context"] if window else previous_context
            steps.append({
                "step": entry["step"],
                "item": entry["item"],
                "result": entry["result"],
                "calls": len(window),
                "context_end": end_context,
                "growth": (end_context - previous_context)
                if end_context is not None and previous_context is not None else None,
                "output_tokens": sum(c["output"] for c in window),
                "reads": [{"file": r["file"], "bytes": r["bytes"]} for r in step_reads],
            })
            previous_context = end_context
        read_counts: dict[str, dict] = {}
        for step in steps:
            for r in step["reads"]:
                agg = read_counts.setdefault(r["file"], {"count": 0, "bytes": []})
                agg["count"] += 1
                agg["bytes"].append(r["bytes"])
        items = {}
        for step in steps:
            if step["item"] is not None and step["growth"] is not None:
                items[step["item"]] = items.get(step["item"], 0) + step["growth"]
        reports.append({
            "run": run["path"],
            "skill": run["skill"],
            "context_before": start_context,
            "context_after": previous_context,
            "steps": steps,
            "reads": read_counts,
            "per_item_growth": items,
        })
    return reports


def format_text(reports: list[dict], subagent_calls: int) -> str:
    def n(value) -> str:
        return "-" if value is None else f"{value:,}"

    out = ["# context = input + cache creation + cache read tokens of the step's last API call"]
    for rep in reports:
        out.append("")
        out.append(f"== {rep['skill']} ({rep['run']})")
        out.append(f"   context before the run: {n(rep['context_before'])}")
        for step in rep["steps"]:
            label = step["step"] + (f" | {step['item']}" if step["item"] is not None else "")
            out.append(f"   {label:<60} {step['result']:<10} calls={step['calls']:<3} "
                       f"context={n(step['context_end'])} growth={n(step['growth'])}")
            for r in step["reads"]:
                out.append(f"       READ {r['file']} ({n(r['bytes'])} B returned)")
        out.append(f"   context after the run: {n(rep['context_after'])}")
        for name, size in rep["per_item_growth"].items():
            out.append(f"   PER ITEM {name}: growth={n(size)}")
        for name, agg in sorted(rep["reads"].items()):
            sizes = ", ".join(n(b) for b in agg["bytes"])
            out.append(f"   READS {name}: {agg['count']} time(s) ({sizes} B)")
    out.append("")
    out.append(f"subagent calls (not in the main context): {subagent_calls}")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--run", action="append", required=True, help="a run record (repeatable)")
    parser.add_argument("--log", action="append", required=True,
                        help="a Claude Code conversation log .jsonl (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        runs = sorted((read_run(Path(p)) for p in args.run), key=lambda r: r["started_at"])
        calls, reads, subagent_calls = read_logs([Path(p) for p in args.log])
    except MeasureError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    reports = measure(runs, calls, reads)
    if args.json:
        print(json.dumps({"runs": reports, "subagent_calls": subagent_calls},
                         ensure_ascii=False, indent=2))
    else:
        print(format_text(reports, subagent_calls))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
