"""What every Skill's `workflow_checks.py` reads the same way (Issue #1219).

Each Skill that runs on `skill_workflow.py` keeps its own `scripts/workflow_checks.py`
— the knowledge of what its steps leave on disk. Those used to be written to stand
alone, so the helpers they share were copied into each one, and the copies had
started to drift: `read_markdown` returned `(frontmatter, body)` in two Skills and
the frontmatter alone in a third, and the two `records_since` took different
arguments and returned different things. Fixing how a run record or a review record
is read meant finding every copy.

The helpers live here, once, and each `workflow_checks.py` imports them from
`.wikicommit/scripts/` — where every script used by more than one Skill lives. What stays in each Skill is what differs: how its
arguments are parsed, which paths its steps write, what a finished step looks like.

**The run record's state key is read in one place only.** `read_run()` hands the
record to `skill_workflow.run_state()`, so the key the engine writes under and the old
key it still reads (`driver:`) are decided by the engine alone; a change to either is
made there and reaches every Skill's checks.
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text
from skill_workflow import parse_porcelain_z, run_command, run_state

# Every child a Skill's checks run is read as UTF-8 and a Python child is told to
# write it, whatever the locale says. One function, the engine's, so the checks and
# the engine that reads their `ITEM:` lines cannot disagree (see its docstring).
run = run_command

REVIEW_DIR = Path(".wikicommit/review")

# The batch-cap question (`batch-cap` with `all` / `first-five`) is asked the same
# way by every Skill that processes a list of items.
BATCH_CAP = 5


# --- files and run records ----------------------------------------------------


def read_markdown(path: Path) -> tuple[dict, str]:
    """(frontmatter, body) of a Markdown file.

    The frontmatter is `{}` when there is none, it cannot be parsed, or the file
    cannot be read; the body is "" only when the file cannot be read.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError:
        return {}, ""
    front, _, body = parse_frontmatter_and_body_text(text)
    return (front if isinstance(front, dict) else {}), body


def read_run(run: str) -> tuple[dict, dict]:
    """(run record, engine state). The state is `{}` for a record the engine did
    not open, so a check reads it as "nothing recorded" rather than failing."""
    record, _ = read_markdown(Path(run))
    return record, run_state(record) or {}


def listed(state: dict, name: str) -> list[str]:
    """A list the run holds (`produces:` or `done --add`), as strings."""
    lists = state.get("lists")
    values = lists.get(name) if isinstance(lists, dict) else None
    return [str(v) for v in values] if isinstance(values, list) else []


def answer_of(state: dict, step: str) -> str:
    """The first answer recorded for a `human` step, or ""."""
    log = state.get("log")
    for entry in log if isinstance(log, list) else []:
        if isinstance(entry, dict) and entry.get("step") == step and entry.get("answer"):
            return str(entry["answer"])
    return ""


def run_started(record: dict) -> datetime | None:
    """The run record's `started_at` as a naive local time to the second, or None
    when it cannot be read.

    Local time because `record_review.py` names its records in local time; to the
    second because that is all a record's name carries.
    """
    try:
        started = datetime.fromisoformat(str(record.get("started_at") or ""))
    except ValueError:
        return None
    if started.tzinfo is not None:
        started = started.astimezone().replace(tzinfo=None)
    return started.replace(microsecond=0)


def written_since(path: Path, since: datetime) -> bool:
    """True when the file exists and was modified at or after `since`."""
    if not path.is_file():
        return False
    return datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0) >= since


def norm(path: str) -> str:
    """Repository-relative POSIX path (an absolute path under the working directory
    is made relative; `..` and `.` are folded)."""
    raw = Path(str(path))
    if raw.is_absolute():
        try:
            raw = raw.relative_to(Path.cwd())
        except ValueError:
            pass
    return Path(os.path.normpath(str(raw))).as_posix()


def git(*args: str) -> subprocess.CompletedProcess:
    """`git <args>` with output captured as UTF-8; exit 127 when git cannot be run."""
    return run(["git", *args])


def review_record_dir(page: str) -> Path:
    """Where `record_review.py` writes the review records of `page`, a
    repository-relative path under `.wikicommit/`."""
    return REVIEW_DIR / Path(page).relative_to(".wikicommit").with_suffix("")


def review_records_since(page: str, since: datetime, stage: str,
                         result: str | None = None) -> list[tuple[Path, dict]]:
    """The page's review records of `stage` (and `result`, when given) written at
    or after `since`, oldest first, as (path, frontmatter).

    `page` is a repository-relative path under `.wikicommit/` (pass it through the
    caller's `norm` first). `record_review.py` names each record
    `<YYYYMMDD>-<HHMMSS>-<kind>.md` in local time — the clock `run_started()` reads
    `started_at` in — so a record from an earlier run on the same page does not
    complete this one. A file whose name carries no timestamp is not a record.
    """
    directory = review_record_dir(page)
    found = []
    for path in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        try:
            stamp = datetime.strptime(path.name[:15], "%Y%m%d-%H%M%S")
        except ValueError:
            continue
        if stamp < since:
            continue
        front, _ = read_markdown(path)
        if str(front.get("stage") or "") != stage:
            continue
        if result is not None and str(front.get("result") or "") != result:
            continue
        found.append((path, front))
    return found


# --- subcommands shared as they are -------------------------------------------


def cmd_over_cap(args, noun: str = "item") -> int:
    """True when the run's `--list` holds more than BATCH_CAP items (ask the person)."""
    _, state = read_run(args.run)
    items = listed(state, args.list)
    if len(items) > BATCH_CAP:
        return 0
    print(f"{len(items)} {noun}(s); no more than {BATCH_CAP}, so nothing to ask")
    return 1


def cmd_select(args) -> int:
    """Apply the batch-cap answer to the collected list."""
    _, state = read_run(args.run)
    items = listed(state, args.list)
    if answer_of(state, args.answer_step) == "first-five":
        items = items[:BATCH_CAP]
    for item in items:
        print(f"ITEM: {item}")
    return 0
