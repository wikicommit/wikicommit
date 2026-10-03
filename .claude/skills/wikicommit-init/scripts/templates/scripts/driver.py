#!/usr/bin/env python3
"""driver.py — hold the progress of a multi-step Skill run in a script (Issue #1085).

A long Skill used to be run from memory: the agent read the whole procedure and
kept track of where it was. Every failure found in the published pilots had that
shape — a step at the tail that did not run (#406), a write-back that did not
happen (#474), a result that was not handed on (#452), a part that was improvised
because it was only prose (#947). Each was fixed by moving *that one step* into a
script. This moves the progression itself.

The division of labour:

- **The driver holds progress.** `next` returns exactly one step. The agent does
  not need to remember the procedure, and after a compaction or a new session it
  calls `next` again and gets the same step.
- **The agent holds judgment.** An `agent` step is carried out exactly as before,
  by reading its instructions file. A `human` step is asked by the agent and the
  answer is handed back. A `script` step is run by the driver itself.
- **Completion is decided on disk, not by the agent's word.** `done` runs the
  step's check script and refuses to mark the step complete when it fails. When
  the step's instructions file declares a `pass_token`, `done` also refuses
  unless the same token is passed — the driver opens the file itself, so the
  caller cannot point it at a file of its own.
- **The driver keeps no state in memory.** Everything lives in the run record
  (`record_run.py`), under a `driver:` key, and the next step is recomputed from
  the log on every call. The log *is* the state, so "the log says done but the
  work was not" cannot arise from the driver's own bookkeeping.
- **The driver writes the log, never the agent.** An instruction to "record this"
  is itself a step that can be forgotten.

## What this engine knows and does not know

It knows the workflow definition format (below), the run record (through
`record_run.py`) and Git's `status --porcelain`. It does not know any path under
`.wikicommit/`, any `status:` value, or any pass name — those live in each Skill's
workflow file and its check scripts. That separation is what lets a second Skill
use the same engine.

## Workflow definition

A YAML file inside the Skill directory:

    skill: wikicommit-generate          # the run record's `skill`
    steps:
      - id: preflight
        type: script                    # the driver runs it
        run: ["{python}", "{skill_dir}/scripts/x.py", preflight, --run, "{run}"]
      - id: register
        type: agent                     # the agent carries it out
        when: [python, ...]             # exit 0: run the step; exit 1: skip it
        instructions: references/step0.md
        outcomes: {registered: "...", nothing: "..."}
        finishes_on: [nothing]          # this outcome ends the run normally
        adds: [registered]              # lists `done --add NAME=VALUE` may extend
        check: [python, ..., --outcome, "{outcome}"]
      - id: batch-cap
        type: human                     # the agent asks the person
        ask: "..."
        choices: {all: "...", first-five: "..."}
        non_interactive: first-five     # the answer used when nobody is there
      - id: collect
        type: script
        run: [...]
        produces: sources               # stdout `ITEM: <value>` lines become a list
        finish_if_empty: "No management files to process"
      - id: per-source
        for_each: sources               # the nested steps repeat per item
        steps:
          - id: pass1-extract
            type: agent
            instructions: references/pass1-extract.md
            stamp: true                 # also written to the record's `passes`
            outcomes: {...}
            ends_item_on: [failed]      # the rest of this item's steps are skipped
            halts_on: [halted]          # the run stops (needs `done --reason`)
            check_on_halt: false        # (optional) run `check` on a halting outcome too

Commands are argv lists and run from the repository root without a shell. The
placeholders `{python}` (the interpreter running the driver), `{skill_dir}`,
`{run}`, `{item}` and `{outcome}` are substituted per argument. A check prints `TOUCHED: <path>` for every file it confirmed the step
wrote; those join the run's `touched` list, which `check-merge` reads.

## Not proof against fabrication

Every layer here stands on files the agent can also write: it could edit the run
record, write the files a check looks at without doing the work, or grep a token
out of a file without reading the rest. A script in the same sandbox cannot tell
its own writes from the agent's. What this catches is forgetting and skipping,
which is every failure recorded so far; it does not catch deliberate falsehood.
"""

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

import record_run  # noqa: E402

STEP_TYPES = ("agent", "human", "script")

# Consecutive failed checks on one step before `next` says to stop and ask a
# person. A check that keeps failing is either a real problem with the work or a
# problem with the check, and neither is fixed by trying a fourth time.
MAX_CHECK_FAILURES = 3

STATE_RUNNING = "running"
STATE_FINISHED = "finished"
STATE_HALTED = "halted"
STATE_ABANDONED = "abandoned"


class DriverError(Exception):
    """A usage problem or a broken workflow definition."""


# --- workflow definition ------------------------------------------------------


def load_workflow(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise DriverError(f"{path}: workflow definition cannot be read: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise DriverError(f"{path}: a workflow needs a `steps:` list")
    if not data.get("skill"):
        raise DriverError(f"{path}: a workflow needs a `skill:`")
    seen: set[str] = set()
    _validate_steps(path, data["steps"], seen)
    return data


def _validate_steps(path: Path, steps: list, seen: set[str]) -> None:
    for step in steps:
        if not isinstance(step, dict) or not step.get("id"):
            raise DriverError(f"{path}: every step needs an `id`")
        sid = str(step["id"])
        if sid in seen:
            raise DriverError(f"{path}: step id {sid!r} is used twice")
        seen.add(sid)
        if "for_each" in step:
            if not isinstance(step.get("steps"), list):
                raise DriverError(f"{path}: {sid}: `for_each` needs nested `steps:`")
            _validate_steps(path, step["steps"], seen)
            continue
        if step.get("type") not in STEP_TYPES:
            raise DriverError(
                f"{path}: {sid}: `type` must be one of {', '.join(STEP_TYPES)}"
            )
        if step["type"] == "script" and not step.get("run"):
            raise DriverError(f"{path}: {sid}: a script step needs `run:`")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def outcome_names(step: dict) -> list[str]:
    outcomes = step.get("outcomes")
    if isinstance(outcomes, dict):
        return [str(k) for k in outcomes]
    if isinstance(outcomes, list):
        return [str(k) for k in outcomes]
    return ["done"]


def choice_names(step: dict) -> list[str]:
    choices = step.get("choices")
    if isinstance(choices, dict):
        return [str(k) for k in choices]
    if isinstance(choices, list):
        return [str(k) for k in choices]
    return []


# --- run record ---------------------------------------------------------------


def load_run(run: Path) -> tuple[dict, dict]:
    if not run.is_file():
        raise DriverError(f"{run}: no such run record (pass the path `start` printed)")
    try:
        record = record_run.read_record(run)
    except record_run.RunError as e:
        raise DriverError(str(e)) from e
    state = record.get("driver")
    if not isinstance(state, dict):
        raise DriverError(f"{run}: this run was not opened by driver.py")
    return record, state


def save_run(run: Path, record: dict, state: dict) -> None:
    record["driver"] = state
    record_run.write_record(run, record)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def item_key(step_id: str, item: str | None) -> str:
    return f"{step_id}|{item}" if item is not None else step_id


# --- substitution and commands ------------------------------------------------


def substitute(argv, mapping: dict[str, str]) -> list[str]:
    if isinstance(argv, str):
        argv = shlex.split(argv)
    out = []
    for arg in argv:
        text = str(arg)
        for key, value in mapping.items():
            text = text.replace("{" + key + "}", value)
        out.append(text)
    return out


def run_command(argv: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as e:
        return subprocess.CompletedProcess(argv, 127, "", f"ERROR: cannot run {argv[0]}: {e}")


def parse_items(stdout: str) -> list[str]:
    items: list[str] = []
    for line in stdout.splitlines():
        if line.startswith("ITEM: "):
            value = line[len("ITEM: "):].strip()
            if value and value not in items:
                items.append(value)
    return items


def parse_touched(stdout: str) -> list[str]:
    return [
        line[len("TOUCHED: "):].strip()
        for line in stdout.splitlines()
        if line.startswith("TOUCHED: ") and line[len("TOUCHED: "):].strip()
    ]


# --- replay -------------------------------------------------------------------


def _done_keys(state: dict) -> set[str]:
    return {entry["key"] for entry in state.get("log", []) if isinstance(entry, dict)}


def _ended_items(state: dict) -> set[str]:
    return {
        str(entry.get("item"))
        for entry in state.get("log", [])
        if isinstance(entry, dict) and entry.get("ends_item")
    }


def current_step(workflow: dict, state: dict):
    """The first step not yet in the log, as `(step, item)`, or None when done.

    Pure: it reads the log and the lists and changes nothing. `when` conditions and
    script steps are resolved by `advance()`, which records them, so by the time a
    step comes back from here unresolved it is one the agent or a person has to do.
    """
    done = _done_keys(state)
    ended = _ended_items(state)
    lists = state.get("lists", {})
    for step in workflow["steps"]:
        if "for_each" in step:
            for item in lists.get(str(step["for_each"]), []):
                if str(item) in ended:
                    continue
                for sub in step["steps"]:
                    if item_key(sub["id"], item) not in done:
                        return sub, str(item)
            continue
        if item_key(step["id"], None) not in done:
            return step, None
    return None


def find_step(workflow: dict, step_id: str) -> dict | None:
    for step in workflow["steps"]:
        if "for_each" in step:
            for sub in step["steps"]:
                if sub["id"] == step_id:
                    return sub
        elif step["id"] == step_id:
            return step
    return None


def _log(state: dict, step: dict, item: str | None, **fields) -> dict:
    entry = {"key": item_key(step["id"], item), "step": step["id"], "at": now_iso()}
    if item is not None:
        entry["item"] = item
    entry.update({k: v for k, v in fields.items() if v not in (None, "", [])})
    state.setdefault("log", []).append(entry)
    return entry


def _touch(state: dict, paths) -> None:
    touched = state.setdefault("touched", [])
    for path in paths:
        if path and path not in touched:
            touched.append(path)


def _record_sources(record: dict, state: dict) -> None:
    sources_list = state.get("record_sources")
    if sources_list:
        record["sources"] = list(state.get("lists", {}).get(sources_list, []))


def _finish(record: dict, state: dict, reason: str = "") -> None:
    state["state"] = STATE_FINISHED
    record["ended_at"] = record.get("ended_at") or now_iso()
    if reason:
        state["finished_because"] = reason
    _record_sources(record, state)


def _halt(record: dict, state: dict, reason: str, new_state: str = STATE_HALTED) -> None:
    state["state"] = new_state
    record["ended_at"] = record.get("ended_at") or now_iso()
    record["halted_reason"] = reason
    _record_sources(record, state)


def advance(ctx: dict, record: dict, state: dict, notes: list[str]):
    """Resolve every step that needs no agent: conditions, scripts, and human
    steps in a non-interactive run. Returns the step the caller must do, or None.

    The record is saved before every command runs, because conditions and scripts
    read the run record themselves — a list produced one step earlier must already
    be on disk when the next step's script looks for it.
    """
    workflow = ctx["workflow"]
    run = ctx["run"]
    while state.get("state") == STATE_RUNNING:
        found = current_step(workflow, state)
        if found is None:
            _finish(record, state)
            return None
        step, item = found
        mapping = ctx["mapping"](item, "")
        when = step.get("when")
        if when:
            save_run(run, record, state)
            result = run_command(substitute(when, mapping))
            if result.returncode == 1:
                _log(state, step, item, outcome="skipped")
                continue
            if result.returncode != 0:
                raise DriverError(
                    f"{step['id']}: condition failed with exit {result.returncode}: "
                    f"{(result.stderr or result.stdout).strip()}"
                )
        if step["type"] == "script":
            save_run(run, record, state)
            result = run_command(substitute(step["run"], mapping))
            output = [line for line in result.stdout.splitlines() if line.strip()]
            notes.extend(line for line in output if not line.startswith(("ITEM: ", "TOUCHED: ")))
            notes.extend(line for line in result.stderr.splitlines() if line.strip())
            if result.returncode != 0:
                reason = next(
                    (line for line in reversed(output + result.stderr.splitlines()) if line.strip()),
                    f"exit {result.returncode}",
                )
                _log(state, step, item, outcome="halted", note=reason)
                _halt(record, state, f"{step['id']}: {reason}")
                return None
            _touch(state, parse_touched(result.stdout))
            produced = step.get("produces")
            if produced:
                state.setdefault("lists", {})[str(produced)] = parse_items(result.stdout)
            _log(state, step, item, outcome="ran")
            if produced and step.get("finish_if_empty") and not state["lists"][str(produced)]:
                notes.append(str(step["finish_if_empty"]))
                _finish(record, state, str(step["finish_if_empty"]))
                return None
            continue
        if step["type"] == "human" and not state.get("interactive", True):
            answer = step.get("non_interactive")
            if answer is None:
                raise DriverError(
                    f"{step['id']}: no answer is defined for a run with nobody to ask "
                    "(`non_interactive:`)"
                )
            _log(state, step, item, answer=str(answer), answered_by="non-interactive default")
            notes.append(f"{step['id']}: no one to ask, so the answer is {answer!r}")
            continue
        return step, item
    return None


# --- responses ----------------------------------------------------------------


def describe(ctx: dict, run: Path, record: dict, state: dict, found, notes: list[str]) -> dict:
    response: dict = {"run": str(run)}
    if notes:
        response["notes"] = notes
    if found is None:
        response["step"] = None
        response["state"] = state.get("state")
        if state.get("state") == STATE_FINISHED:
            response["finished"] = True
            if state.get("finished_because"):
                response["finished_because"] = state["finished_because"]
        else:
            response["halted_reason"] = record.get("halted_reason", "")
        return response

    step, item = found
    driver = f"python {ctx['driver_path']}"
    response.update({"step": step["id"], "type": step["type"]})
    if item is not None:
        response["item"] = item
    key = item_key(step["id"], item)
    failures = state.get("failures", {}).get(key, 0)
    if failures:
        response["previous_check_failures"] = failures
    if failures >= MAX_CHECK_FAILURES:
        response["blocked"] = True
        response["message"] = (
            f"The completion check for this step has failed {failures} times. Stop, "
            "report the last failure to the person running this, and do not work "
            "around the check."
        )
    item_arg = f" --item {shlex.quote(item)}" if item is not None else ""
    base = f"{driver} done {shlex.quote(str(run))} --step {step['id']}{item_arg}"

    if step["type"] == "human":
        response["ask"] = step.get("ask", "")
        response["choices"] = step.get("choices", {})
        response["then"] = f"{base} --answer <choice>"
        return response

    if step.get("instructions"):
        response["instructions"] = step["instructions"]
    if step.get("also_read"):
        response["also_read"] = step["also_read"]
    response["outcomes"] = step.get("outcomes") or {"done": ""}
    token = pass_token_for(ctx, step)
    token_arg = " --token <the pass_token in the instructions file>" if token else ""
    halts = [str(o) for o in step.get("halts_on", [])]
    reason_arg = " [--reason <why> when halting]" if halts else ""
    adds = step.get("adds") or []
    add_arg = "".join(f" [--add {name}=<value> ...]" for name in adds)
    response["then"] = f"{base} --outcome <one of outcomes>{token_arg}{reason_arg}{add_arg}"
    response["interactive"] = bool(state.get("interactive", True))
    if not state.get("interactive", True) and step.get("non_interactive"):
        response["when_nobody_can_answer"] = step["non_interactive"]
    return response


def pass_token_for(ctx: dict, step: dict) -> str | None:
    instructions = step.get("instructions")
    if not instructions:
        return None
    return record_run.read_pass_token(ctx["skill_dir"] / str(instructions))


# --- context ------------------------------------------------------------------


def build_context(workflow_path: Path, run: Path | None) -> dict:
    workflow = load_workflow(workflow_path)
    skill_dir = workflow_path.parent

    def mapping(item: str | None, outcome: str) -> dict[str, str]:
        return {
            "python": sys.executable,
            "skill_dir": str(skill_dir),
            "run": str(run) if run else "",
            "item": item or "",
            "outcome": outcome,
        }

    return {
        "run": run,
        "workflow": workflow,
        "workflow_path": workflow_path,
        "skill_dir": skill_dir,
        "mapping": mapping,
        "driver_path": _repo_relative(Path(__file__).absolute()),
    }


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def context_for_run(run: Path, record: dict, state: dict) -> tuple[dict, list[str]]:
    workflow_path = Path(str(state.get("workflow", "")))
    if not workflow_path.is_file():
        raise DriverError(
            f"{workflow_path}: the workflow this run was started with is gone; "
            "abandon the run and start again"
        )
    ctx = build_context(workflow_path, run)
    notes: list[str] = []
    if state.get("workflow_sha256") and state["workflow_sha256"] != file_sha256(workflow_path):
        notes.append(
            "WARNING: the workflow definition changed after this run started "
            "(the Skill was updated mid-run); continuing from the recorded log"
        )
    for entry in state.get("log", []):
        if isinstance(entry, dict) and find_step(ctx["workflow"], str(entry.get("step"))) is None:
            raise DriverError(
                f"step {entry.get('step')!r} in this run's log no longer exists in "
                f"{workflow_path}; abandon this run and start a new one"
            )
    return ctx, notes


# --- commands -----------------------------------------------------------------


def cmd_start(args) -> dict:
    workflow_path = Path(args.workflow)
    ctx = build_context(workflow_path, None)
    skill = str(ctx["workflow"]["skill"])
    if skill not in record_run.SKILLS:
        raise DriverError(f"{skill}: not a Skill record_run.py records")
    state = {
        "workflow": workflow_path.as_posix(),
        "workflow_sha256": file_sha256(workflow_path),
        "interactive": not args.non_interactive,
        "state": STATE_RUNNING,
        "lists": {},
        "log": [],
        "failures": {},
        "touched": [],
        "record_sources": ctx["workflow"].get("record_sources", ""),
    }
    run = record_run.open_record(skill, args.model, args.args, extra={"driver": state})
    record, state = load_run(run)
    ctx, notes = context_for_run(run, record, state)
    found = advance(ctx, record, state, notes)
    save_run(run, record, state)
    return describe(ctx, run, record, state, found, notes)


def cmd_next(args) -> dict:
    run = Path(args.run)
    record, state = load_run(run)
    ctx, notes = context_for_run(run, record, state)
    found = advance(ctx, record, state, notes) if state.get("state") == STATE_RUNNING else None
    save_run(run, record, state)
    return describe(ctx, run, record, state, found, notes)


def _parse_adds(pairs: list[str], allowed: list[str]) -> dict[str, list[str]]:
    adds: dict[str, list[str]] = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not name or not value:
            raise DriverError(f"--add expects NAME=VALUE, got: {pair}")
        if name not in allowed:
            raise DriverError(
                f"--add {name}: this step may add to {', '.join(allowed) or 'no list'}"
            )
        adds.setdefault(name, []).append(value)
    return adds


def cmd_done(args) -> tuple[dict, int]:
    run = Path(args.run)
    record, state = load_run(run)
    ctx, notes = context_for_run(run, record, state)
    if state.get("state") != STATE_RUNNING:
        raise DriverError(f"this run is {state.get('state')}; there is no step to complete")
    found = advance(ctx, record, state, notes)
    if found is None:
        save_run(run, record, state)
        return describe(ctx, run, record, state, found, notes), 0
    step, item = found

    def refuse(reason: str, count: bool = False) -> tuple[dict, int]:
        if count:
            key = item_key(step["id"], item)
            state.setdefault("failures", {})[key] = state.get("failures", {}).get(key, 0) + 1
        save_run(run, record, state)
        response = describe(ctx, run, record, state, found, notes)
        response["accepted"] = False
        response["reason"] = reason
        return response, 1

    # Order is enforced: only the step `next` would return can be completed.
    if args.step != step["id"] or (args.item or None) != item:
        where = f"{step['id']}" + (f" for {item}" if item is not None else "")
        return refuse(f"the current step is {where}; {args.step} cannot be completed now")

    if step["type"] == "human":
        choices = choice_names(step)
        if not args.answer or (choices and args.answer not in choices):
            return refuse(f"--answer must be one of: {', '.join(choices)}")
        _log(state, step, item, answer=args.answer, answered_by="person")
        return _after_done(ctx, run, record, state, notes)

    outcome = args.outcome or ("done" if outcome_names(step) == ["done"] else "")
    if outcome not in outcome_names(step):
        return refuse(f"--outcome must be one of: {', '.join(outcome_names(step))}")

    token_state = record_run.TOKEN_UNCHECKED
    declared = pass_token_for(ctx, step)
    if declared is not None:
        if not args.token:
            return refuse(
                f"this step's instructions ({step['instructions']}) declare a pass_token; "
                "read that file and pass --token", count=True,
            )
        if args.token != declared:
            return refuse(
                f"--token does not match the pass_token in {step['instructions']} "
                "(read the file before carrying out the step)", count=True,
            )
        token_state = record_run.TOKEN_OK
    elif step.get("instructions") and not (ctx["skill_dir"] / str(step["instructions"])).is_file():
        return refuse(f"{step['instructions']}: the instructions file for this step is missing")

    halts = [str(o) for o in step.get("halts_on", [])]
    if outcome in halts and not args.reason:
        return refuse("halting needs --reason")

    adds = _parse_adds(args.add, [str(a) for a in step.get("adds") or []])

    touched: list[str] = []
    # A halting outcome skips the check unless the step asks for it: most halts
    # (a missing package) leave nothing on disk to check, but one that writes a
    # deferral first has to be held to it like any other.
    if step.get("check") and (outcome not in halts or step.get("check_on_halt")):
        # Additions are visible to the check through the record, so write them
        # first and roll back on failure.
        before = json.loads(json.dumps(state.get("lists", {})))
        for name, values in adds.items():
            existing = state.setdefault("lists", {}).setdefault(name, [])
            existing.extend(v for v in values if v not in existing)
        save_run(run, record, state)
        result = run_command(substitute(step["check"], ctx["mapping"](item, outcome)))
        # (the additions were saved above so the check can read them)
        if result.returncode != 0:
            state["lists"] = before
            message = (result.stdout + result.stderr).strip() or f"exit {result.returncode}"
            return refuse(f"completion check failed: {message}", count=True)
        touched = parse_touched(result.stdout)
    else:
        for name, values in adds.items():
            existing = state.setdefault("lists", {}).setdefault(name, [])
            existing.extend(v for v in values if v not in existing)

    _touch(state, touched + list(args.touched))
    if item is not None and Path(item).exists():
        _touch(state, [item])
    ends = outcome in [str(o) for o in step.get("ends_item_on", [])]
    _log(state, step, item, outcome=outcome, token=token_state if declared else None,
         ends_item=True if ends else None, note=args.reason or None)
    state.get("failures", {}).pop(item_key(step["id"], item), None)

    if step.get("stamp"):
        passes = record.get("passes")
        record["passes"] = ([*passes] if isinstance(passes, list) else []) + [
            record_run.make_stamp(step["id"], token_state, item or "")
        ]
    if args.count:
        try:
            record.setdefault("outcome", {}).update(record_run.parse_outcome(args.count))
        except record_run.RunError as e:
            raise DriverError(str(e)) from e
    if args.page:
        pages = record.get("pages") if isinstance(record.get("pages"), list) else []
        record["pages"] = pages + [p for p in args.page if p not in pages]

    if outcome in halts:
        _halt(record, state, f"{step['id']}: {args.reason}")
    elif outcome in [str(o) for o in step.get("finishes_on", [])]:
        _finish(record, state, f"{step['id']}: {outcome}")
    return _after_done(ctx, run, record, state, notes)


def _after_done(ctx, run, record, state, notes) -> tuple[dict, int]:
    found = advance(ctx, record, state, notes) if state.get("state") == STATE_RUNNING else None
    save_run(run, record, state)
    response = describe(ctx, run, record, state, found, notes)
    response["accepted"] = True
    return response, 0


def open_runs(run_dir: Path) -> list[tuple[Path, dict, dict]]:
    runs = []
    if not run_dir.is_dir():
        return runs
    for path in sorted(run_dir.glob("*.md"), key=record_run.run_sort_key):
        try:
            record = record_run.read_record(path)
        except (record_run.RunError, OSError):
            continue
        state = record.get("driver")
        if isinstance(state, dict) and state.get("state") == STATE_RUNNING:
            runs.append((path, record, state))
    return runs


def cmd_status(args) -> tuple[dict, int]:
    runs = open_runs(record_run.RUN_DIR)
    items = []
    for path, record, state in runs:
        entry = {"run": str(path), "skill": record.get("skill"),
                 "started_at": record.get("started_at")}
        try:
            ctx, _ = context_for_run(path, record, state)
            found = current_step(ctx["workflow"], state)
            if found is not None:
                entry["step"] = found[0]["id"]
                if found[1] is not None:
                    entry["item"] = found[1]
        except DriverError as e:
            entry["problem"] = str(e)
        items.append(entry)
    return {"open_runs": items}, 0


def stop_hook_response(stdin_text: str) -> dict | None:
    """What a Stop hook prints: a block while a run is open, nothing otherwise.

    Blocking only once per stop attempt (`stop_hook_active`) keeps a dead run from
    a previous session from trapping every later session in a loop: the reason
    tells the agent how to abandon it.
    """
    try:
        payload = json.loads(stdin_text) if stdin_text.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if isinstance(payload, dict) and payload.get("stop_hook_active"):
        return None
    runs = open_runs(record_run.RUN_DIR)
    if not runs:
        return None
    path = runs[-1][0]
    driver = _repo_relative(Path(__file__).absolute())
    return {
        "decision": "block",
        "reason": (
            f"A run is still open: {path}. Run `python {driver} next "
            f"{path}` and follow it until it reports finished. If that run belongs to a "
            f"session that is gone, ask the person whether to abandon it "
            f"(`driver.py abandon {path} --reason <why>`)."
        ),
    }


def changed_files() -> list[str]:
    result = run_command(["git", "status", "--porcelain", "--untracked-files=all"])
    if result.returncode != 0:
        raise DriverError(f"git status failed: {result.stderr.strip()}")
    files = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip().strip('"'))
    return files


def cmd_check_merge(args) -> tuple[dict, int]:
    """Block a merge that would carry files an unfinished run touched.

    The question is "is a run still open", not "did every change come through the
    driver": changes from Skills that use no driver, and hand edits, are legitimate
    and pass. A run that halted, finished or was abandoned is not open.
    """
    changed = list(args.changed) if args.changed else changed_files()
    changed_set = set(changed)
    blocking = []
    for path, record, state in open_runs(record_run.RUN_DIR):
        overlap = [p for p in state.get("touched", []) if p in changed_set]
        if not overlap:
            continue
        entry = {"run": str(path), "skill": record.get("skill"), "files": overlap}
        try:
            ctx, _ = context_for_run(path, record, state)
            found = current_step(ctx["workflow"], state)
            if found is not None:
                entry["step"] = found[0]["id"]
                if found[1] is not None:
                    entry["item"] = found[1]
        except DriverError as e:
            entry["problem"] = str(e)
        blocking.append(entry)
    if blocking:
        return {
            "blocked": True,
            "open_runs": blocking,
            "message": (
                "An unfinished run touched files in this change. Continue it with "
                "`driver.py next <run>` until it finishes, or, if its session is gone, "
                "abandon it with `driver.py abandon <run> --reason <why>` after a person "
                "has decided what to do with the files it left."
            ),
        }, 1
    return {"blocked": False}, 0


def cmd_abandon(args) -> tuple[dict, int]:
    run = Path(args.run)
    record, state = load_run(run)
    if state.get("state") != STATE_RUNNING:
        raise DriverError(f"this run is already {state.get('state')}")
    try:
        changed = set(changed_files())
    except DriverError:
        changed = set()
    left = [p for p in state.get("touched", []) if p in changed]
    _halt(record, state, f"abandoned: {args.reason}", STATE_ABANDONED)
    save_run(run, record, state)
    # Neither passed through nor deleted: the files are named for a person to decide.
    return {"run": str(run), "state": STATE_ABANDONED, "left_behind": left}, 0


# --- CLI ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hold the progress of a multi-step Skill run; return one step at a time."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="open a run and return its first step")
    start.add_argument("--workflow", required=True, help="the Skill's workflow definition")
    start.add_argument("--model", default="", help="runtime-reported model ID")
    start.add_argument("--arg", dest="args", action="append", default=[], metavar="ARG",
                       help="an argument this run was invoked with (repeatable)")
    start.add_argument("--non-interactive", action="store_true",
                       help="nobody can answer questions; human steps take their default")

    nxt = sub.add_parser("next", help="return the current step")
    nxt.add_argument("run")

    done = sub.add_parser("done", help="complete the current step and return the next")
    done.add_argument("run")
    done.add_argument("--step", required=True)
    done.add_argument("--item", default="")
    done.add_argument("--outcome", default="")
    done.add_argument("--answer", default="")
    done.add_argument("--token", default="")
    done.add_argument("--reason", default="")
    done.add_argument("--add", action="append", default=[], metavar="NAME=VALUE")
    done.add_argument("--touched", action="append", default=[], metavar="PATH")
    done.add_argument("--page", action="append", default=[], metavar="PATH",
                      help="a page this run wrote (recorded on the run record)")
    done.add_argument("--count", action="append", default=[], metavar="KEY=VALUE",
                      help="a count for the run record's outcome")

    status = sub.add_parser("status", help="list runs that are still open")
    status.add_argument("--stop-hook", action="store_true",
                        help="read a Stop hook payload on stdin and answer in its format")

    merge = sub.add_parser("check-merge", help="refuse files an unfinished run touched")
    merge.add_argument("changed", nargs="*", help="changed files (default: git status)")

    abandon = sub.add_parser("abandon", help="close a run whose session is gone")
    abandon.add_argument("run")
    abandon.add_argument("--reason", required=True)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "status" and args.stop_hook:
            response = stop_hook_response(sys.stdin.read())
            if response:
                print(json.dumps(response, ensure_ascii=False))
            return 0
        if args.command == "start":
            response, code = cmd_start(args), 0
        elif args.command == "next":
            response, code = cmd_next(args), 0
        elif args.command == "done":
            response, code = cmd_done(args)
        elif args.command == "status":
            response, code = cmd_status(args)
        elif args.command == "check-merge":
            response, code = cmd_check_merge(args)
        else:
            response, code = cmd_abandon(args)
    except (DriverError, record_run.RunError, OSError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
