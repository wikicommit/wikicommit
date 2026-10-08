#!/usr/bin/env python3
"""workflow_checks.py — the wikicommit-synthesize knowledge `skill_workflow.py` does not have.

`skill_workflow.py` walks `workflow.yaml` and knows nothing about this Skill. Which pages
may ground a synthesis, where a view page lands, which frontmatter it must carry
and where its review record goes live here, next to the workflow, so the engine
stays the one the other Skills use.

Every subcommand runs from the repository root and follows the same contract as
the other Skills' checks:

- **exit 0** means yes (a condition holds, a check passed, a command ran)
- **exit 1** means no, with the reason on stdout
- `TOUCHED: <path>` lines are files the check confirmed the step wrote

A run writes at most one view page, so nothing here is a list of work items. The
values one step hands to the next — `topic`, `kind`, `max_grounding`, `grounding`
and `page` — are lists in the run record that `done --add` extends, which is
what lets a resumed step see them without anything held in memory.

These checks confirm consistency, not proof: they catch the step that was
forgotten (a translation used as grounding, a `derived_from` that does not match
what was read, a review not recorded), not one that was faked.
"""

import argparse
import sys
from datetime import datetime
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
    import yaml
    from _workflow_checks import (
        git, listed, norm, read_markdown, read_run, review_records_since, run,
        run_started, written_since,
    )
except ImportError as e:
    if isinstance(e, ModuleNotFoundError) and e.name == "yaml":
        print(f"PyYAML is not installed ({e}); install it (pip install pyyaml) and run again")
    else:
        print(".wikicommit/scripts/ is missing a module this Skill needs or is older than "
              f"this Skill ({e}); run /wikicommit-update first")
    sys.exit(2)

CONFIG = Path(".wikicommit/config.yml")
RULES = Path(".wikicommit/review-rules.md")
ENTITY_PREFIX = ".wikicommit/entity/"
VIEW_PREFIX = ".wikicommit/view/"
REBUILD_SCRIPT = Path(".wikicommit/scripts/rebuild_index.py")
STAGE = "synthesize-step5.5"
DEFAULT_MAX_GROUNDING = 30
KINDS = ("practice", "landscape", "comparison", "pattern", "timeline", "debate")


def run_arguments(record: dict) -> tuple[str, str | None, list[str]]:
    """(topic, --max-grounding value, unknown options) from the arguments the run
    was started with.

    The topic is every argument that is not an option, joined by a space, so a
    topic passed unquoted as several words still reads as one. The cap is None
    when `--max-grounding` was not given, and "" when it was given with no value
    (which preflight refuses rather than silently falling back to the default).
    Any other `--option` is returned so preflight can refuse it instead of
    dropping it from the topic without a word.
    """
    args = record.get("args")
    values = [str(a) for a in args] if isinstance(args, list) else []
    words: list[str] = []
    unknown: list[str] = []
    cap: str | None = None
    i = 0
    while i < len(values):
        value = values[i]
        if value == "--max-grounding":
            cap = values[i + 1] if i + 1 < len(values) else ""
            i += 2
            continue
        if value.startswith("--max-grounding="):
            cap = value.split("=", 1)[1]
        elif value.startswith("--"):
            unknown.append(value)
        else:
            words.append(value)
        i += 1
    return " ".join(w for w in words if w.strip()).strip(), cap, unknown


def primary_lang() -> str:
    try:
        data = yaml.safe_load(CONFIG.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError):
        return ""
    data = data if isinstance(data, dict) else {}
    translation = data.get("translation") if isinstance(data.get("translation"), dict) else {}
    return str(translation.get("primary_lang") or "")


def max_grounding(record: dict, state: dict) -> int | None:
    """The cap Step 1 settles: a number named at the survey wins over the
    argument, and 30 when neither gave one. None when the value is not a number."""
    named = listed(state, "max_grounding")
    _, arg, _ = run_arguments(record)
    raw = named[-1] if named else arg
    if raw is None:
        return DEFAULT_MAX_GROUNDING
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def outcome_of(state: dict, step: str) -> str:
    for entry in reversed(state.get("log", [])):
        if isinstance(entry, dict) and entry.get("step") == step and entry.get("outcome"):
            return str(entry["outcome"])
    return ""


# --- preflight and conditions -------------------------------------------------


def cmd_preflight(args) -> int:
    """Stop before any search when the run could never finish."""
    if not CONFIG.is_file():
        print(".wikicommit/config.yml does not exist; run /wikicommit-init first")
        return 1
    if not RULES.is_file():
        print(".wikicommit/review-rules.md does not exist; run /wikicommit-init "
              "--no-overwrite to install it (the synthesize-step5.5 review cannot run without it)")
        return 1
    if not primary_lang():
        print(".wikicommit/config.yml has no translation.primary_lang")
        return 1
    record, state = read_run(args.run)
    _, raw, unknown = run_arguments(record)
    if unknown:
        print(f"unknown option(s) {', '.join(unknown)}; the only option is --max-grounding <N>")
        return 1
    if max_grounding(record, state) is None:
        print(f"--max-grounding {raw!r} is not a positive whole number")
        return 1
    return 0


def cmd_needs_survey(args) -> int:
    """Survey mode runs only when no topic was given."""
    record, _ = read_run(args.run)
    topic, _, _ = run_arguments(record)
    if topic:
        print(f"a topic was given ({topic!r}); no survey")
        return 1
    return 0


def cmd_wrote_page(args) -> int:
    _, state = read_run(args.run)
    if outcome_of(state, "write") == "written":
        return 0
    print("no view page was written in this run; the view index is left as it is")
    return 1


# --- step checks --------------------------------------------------------------


def cmd_check_survey(args) -> int:
    record, state = read_run(args.run)
    if args.outcome != "chosen":
        return 0
    if not listed(state, "topic"):
        print("no topic was added (pass --add topic=<the chosen topic>)")
        return 1
    kinds = listed(state, "kind")
    if kinds and kinds[-1] not in KINDS:
        print(f"kind {kinds[-1]!r} is not one of {', '.join(KINDS)} (leave it out when none fits)")
        return 1
    if max_grounding(record, state) is None:
        print(f"max_grounding {listed(state, 'max_grounding')[-1]!r} is not a positive whole number")
        return 1
    return 0


def cmd_check_grounding(args) -> int:
    """Every grounding page is a live original in primary_lang, not a translation
    and not itself a synthesis, and there are no more of them than the cap."""
    record, state = read_run(args.run)
    pages = [norm(p) for p in listed(state, "grounding")]
    if args.outcome == "nothing":
        if pages:
            print(f"{len(pages)} grounding page(s) were added, but the outcome says none was found")
            return 1
        return 0
    if not pages:
        print("no grounding page was added (pass --add grounding=<path> for each page read)")
        return 1
    cap = max_grounding(record, state) or DEFAULT_MAX_GROUNDING
    problems = []
    if len(pages) > cap:
        problems.append(f"{len(pages)} grounding pages exceed the cap of {cap}")
    if len(set(pages)) != len(pages):
        problems.append("a grounding page is listed twice")
    prefix = f"{ENTITY_PREFIX}{primary_lang()}/"
    for page in dict.fromkeys(pages):
        if not page.startswith(prefix) or not page.endswith(".md") or page.endswith("/index.md"):
            problems.append(f"{page}: not a page under {prefix} (grounding is original "
                            "pages in primary_lang; a view page never grounds another)")
            continue
        if not Path(page).is_file():
            problems.append(f"{page}: the page does not exist")
            continue
        front, _ = read_markdown(Path(page))
        if front.get("translated_from"):
            problems.append(f"{page}: a translation (translated_from); ground on the original")
        if front.get("derived_from"):
            problems.append(f"{page}: itself a synthesis (derived_from); it cannot ground another")
        if str(front.get("status") or "") == "removed":
            problems.append(f"{page}: removed")
    if problems:
        print("; ".join(problems))
        return 1
    return 0


def view_page(state: dict) -> tuple[str, str]:
    """(page, problem): the path `write` added, checked against where a view page goes."""
    pages = listed(state, "page")
    if not pages:
        return "", "no page path was added (pass --add page=<the view page path>)"
    page = norm(pages[-1])
    lang = primary_lang()
    parts = Path(page).parts
    if not page.startswith(f"{VIEW_PREFIX}{lang}/") or len(parts) != 4 \
            or not page.endswith(".md") or parts[-1] == "index.md":
        return page, f"{page}: a view page goes at {VIEW_PREFIX}{lang}/<slug>.md"
    return page, ""


def last_commit(path: str) -> str:
    log = git("log", "-1", "--format=%H", "--", f":(literal){path}")
    return log.stdout.strip() if log.returncode == 0 else ""


def page_problems(page: str, grounding: list[str]) -> list[str]:
    front, body = read_markdown(Path(page))
    if not front:
        return ["the frontmatter cannot be read"]
    problems = []
    lang = primary_lang()
    if str(front.get("lang") or "") != lang:
        problems.append(f"lang is {front.get('lang')!r}, not {lang!r}")
    if str(front.get("review_status") or "") != "pending":
        problems.append("review_status is not pending")
    for field in ("type", "sources"):
        if field in front:
            problems.append(f"a view page carries no {field}:")
    if "kind" in front and str(front.get("kind")) not in KINDS:
        problems.append(f"kind {front.get('kind')!r} is not one of {', '.join(KINDS)}")
    for field in ("title", "generated_at", "generated_by"):
        if not front.get(field):
            problems.append(f"{field} is not written")
    entries = front.get("derived_from")
    if not isinstance(entries, list) or not entries:
        problems.append("derived_from is not written")
    else:
        seen = {}
        for entry in entries:
            if isinstance(entry, dict) and entry.get("path"):
                seen[norm(str(entry["path"]))] = entry
        wanted = {norm(p) for p in grounding}
        if set(seen) != wanted:
            missing, extra = sorted(wanted - set(seen)), sorted(set(seen) - wanted)
            problems.append("derived_from does not name exactly the grounding pages"
                            + (f" (missing: {', '.join(missing)})" if missing else "")
                            + (f" (not grounding: {', '.join(extra)})" if extra else ""))
        for path, entry in seen.items():
            if path not in wanted:
                continue
            if "source_commit" not in entry:
                problems.append(f"{path}: source_commit is not written")
                continue
            written = "" if entry["source_commit"] is None else str(entry["source_commit"])
            expected = last_commit(path)
            if written != expected:
                problems.append(f"{path}: source_commit is {written!r}, but its last commit is "
                                f"{expected!r}" + (" (no commit yet, so write the empty string)"
                                                   if not expected else ""))
    first = next((line for line in body.splitlines() if line.strip()), "")
    if first.startswith("# "):
        problems.append("the body opens with an H1; the title lives in `title`")
    return problems


def cmd_check_page(args) -> int:
    record, state = read_run(args.run)
    page, problem = view_page(state)
    if problem:
        print(problem)
        return 1
    started = run_started(record)
    if started is None:
        # Every check below compares against the run's start; without it a record
        # or a write from an earlier run would pass for this one, so fail instead.
        print(f"{page}: the run record's started_at ({record.get('started_at')!r}) cannot be "
              "read, so this run's writes and review records cannot be told from earlier ones "
              "(the run record is damaged; start a new run)")
        return 1
    target = Path(page)

    if args.outcome == "declined":
        if not target.is_file():
            print(f"{page}: does not exist, so there was nothing to decline overwriting")
            return 1
        if written_since(target, started):
            print(f"{page}: changed during this run, but overwriting it was declined")
            return 1
        return 0

    wanted = "pass" if args.outcome == "written" else "discarded"
    records = [p for p, _ in review_records_since(norm(page), started, STAGE, wanted)]
    if not records:
        print(f"{page}: no {STAGE} review record with result: {wanted} was written in this run "
              "(record the verdict with record_review.py)")
        return 1

    if args.outcome == "discarded":
        if written_since(target, started):
            print(f"{page}: written during this run, but a discarded synthesis writes nothing "
                  "(restore the previous page, or remove a new one)")
            return 1
        print(f"TOUCHED: {records[-1].as_posix()}")
        return 0

    if not target.is_file():
        print(f"{page}: the page was not written")
        return 1
    if not written_since(target, started):
        print(f"{page}: not written during this run (the file on disk predates it)")
        return 1
    # The pass is recorded after the page is written (Step 5.5 item 6): a page
    # changed after its newest pass record is not the text that record reviewed,
    # and the record's page_content_hash and reviewed_sources would not match it.
    reviewed_at = datetime.strptime(records[-1].name[:15], "%Y%m%d-%H%M%S")
    if datetime.fromtimestamp(target.stat().st_mtime).replace(microsecond=0) > reviewed_at:
        print(f"{page}: changed after its newest {STAGE} pass record "
              f"({records[-1].as_posix()}); record the verdict again for the page as written")
        return 1
    problems = page_problems(page, listed(state, "grounding"))
    if problems:
        print(f"{page}: " + "; ".join(problems))
        return 1
    print(f"TOUCHED: {page}")
    print(f"TOUCHED: {records[-1].as_posix()}")
    return 0


def cmd_rebuild_index(args) -> int:
    """Rebuild the one language index the page was written into (Step 10)."""
    _, state = read_run(args.run)
    page, problem = view_page(state)
    if problem:
        print(problem)
        return 1
    directory = Path(page).parent.as_posix()
    result = run([sys.executable, str(REBUILD_SCRIPT), directory])
    for line in (result.stdout + result.stderr).splitlines():
        if line.strip():
            print(line)
    if result.returncode != 0:
        print(f"{REBUILD_SCRIPT} exited {result.returncode}")
        return 1
    print(f"TOUCHED: {directory}/index.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="wikicommit-synthesize workflow checks")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, outcome=False):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        if outcome:
            p.add_argument("--outcome", default="")
        p.set_defaults(func=func)

    add("preflight", cmd_preflight)
    add("needs-survey", cmd_needs_survey)
    add("wrote-page", cmd_wrote_page)
    add("check-survey", cmd_check_survey, outcome=True)
    add("check-grounding", cmd_check_grounding, outcome=True)
    add("check-page", cmd_check_page, outcome=True)
    add("rebuild-index", cmd_rebuild_index)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
