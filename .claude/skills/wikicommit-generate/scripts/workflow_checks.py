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
# `.wikicommit/scripts/_workflow_checks.py`. A wiki whose scripts predate it has
# none until `/wikicommit-update` is merged.
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


# The other question the end-of-loop step asks: an entity whose type Pass 2c could not
# settle. Such a source is not deferred — it reaches Pass 4, which writes `status: partial`
# with `ambiguous_entities` — so it is found by the management files this run's first-loop
# Pass 4 wrote, not by a deferral.
AMBIGUOUS_STEP = "pass4-review"


def _ambiguous_entities(path: str) -> list[dict]:
    front, _ = read_markdown(Path(path))
    entities = front.get("ambiguous_entities") if front else None
    return [e for e in entities if isinstance(e, dict) and e.get("title")] \
        if isinstance(entities, list) else []


def ambiguous_questions(state: dict) -> dict[str, list[dict]]:
    """{management file: its `ambiguous_entities`} for every source this run's first
    loop left waiting on a type, in the order Pass 4 wrote them."""
    found: dict[str, list[dict]] = {}
    log = state.get("log")
    for entry in log if isinstance(log, list) else []:
        if not (isinstance(entry, dict) and entry.get("step") == AMBIGUOUS_STEP
                and entry.get("item")):
            continue
        item = norm(str(entry["item"]))
        if item in found:
            continue
        entities = _ambiguous_entities(item)
        if entities:
            found[item] = entities
    return found


# A type an `entity-types` answer may name: a Schema.org type, or a custom type spelled
# as `type:` spells it (`schema:custom/Decision`), since that is what the page is written as.
ENTITY_TYPE_NAME = re.compile(r"schema:(?:custom/)?[A-Za-z][A-Za-z0-9_]*")


def parse_entity_type(value: str) -> tuple[str, str, str] | None:
    """(management file, entity title, schema:Type) from an `entity-types` answer,
    written `<management file>#<title>=<schema:Type>`. The file is cut at its `.md#`
    and the type at the last `=`, so a title may hold either character."""
    path, sep, rest = value.partition(".md#")
    if not sep:
        return None
    title, sep, type_name = rest.rpartition("=")
    if not (sep and title.strip() and ENTITY_TYPE_NAME.fullmatch(type_name.strip())):
        return None
    return norm(path + ".md"), title.strip(), type_name.strip()


def entity_type_answers(state: dict) -> dict[tuple[str, str], str]:
    """{(management file, title): schema:Type} for every well-formed `entity-types` answer."""
    answers: dict[tuple[str, str], str] = {}
    for value in listed(state, "entity-types"):
        parsed = parse_entity_type(str(value))
        if parsed:
            answers[(parsed[0], parsed[1])] = parsed[2]
    return answers


def installed_type(name: str) -> bool:
    """True when `schema:<Name>` resolves to a type file: `.wikicommit/schema/<Name>.md`,
    the path a page's `type:` is resolved by (so `schema:custom/X` is `custom/X.md`, and a
    bare `schema:X` does not match a file under `custom/`)."""
    local = name.removeprefix("schema:")
    return local != "default" and (Path(".wikicommit/schema") / f"{local}.md").is_file()


# --- conditions ---------------------------------------------------------------


# Options of a registering run that take the next argument as their value.
VALUE_OPTIONS = ("--include", "--license")


def has_source(values: list[str]) -> bool:
    """True when the arguments name a source to register (one not taken as an option's value)."""
    skip_next = False
    for value in values:
        if skip_next:
            skip_next = False
            continue
        if value in VALUE_OPTIONS:
            skip_next = True
            continue
        if not value.startswith("--"):
            return True
    return False


def cmd_has_source_argument(args) -> int:
    """True when the run was given a source to register (Step 0 applies)."""
    record, _ = read_run(args.run)
    if has_source(run_arguments(record)):
        return 0
    print("no source argument; Step 0 does not apply")
    return 1


# --- preflight ----------------------------------------------------------------


# Scripts this Skill calls from `.wikicommit/scripts/` that used to live in a Skill's own
# `scripts/`. A wiki whose `.wikicommit/scripts/` predates the move has none of them
# until `/wikicommit-update` is merged, and Step 0 would fail on the first command.
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
    # `--license` is recorded only by Step 0's registration. The queue run and
    # `--regenerate` register nothing, so the value would be dropped without a word.
    values = run_arguments(read_run(args.run)[0])
    if any(v == "--license" or v.startswith("--license=") for v in values) and (
            "--regenerate" in values or not has_source(values)):
        print("--license is accepted only together with a source to register; the queue run "
              "and --regenerate register nothing. To record a license on a source already "
              "registered, edit source.license in its management file")
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
    deferred = deferred_questions(state)
    for path in deferred:
        print(f"ITEM: {path}")
    for path in ambiguous_questions(state):
        if path not in deferred:
            print(f"ITEM: {path}")
    return 0


def cmd_halted_questions(args) -> int:
    """The questions a run that stopped part-way set aside and never asked.

    A halt ends the run at once, so `ask-deferred` is never reached; the deferrals stay
    queued, and a later run asks them only if it picks the source again and reaches the
    end of its loop. This lists them for the halt report, each with the first line of its
    reason, so the person learns of them now. It reads the run's log and changes nothing.

    A run that halts in `per-answered-source` has already been through `ask-deferred`:
    its questions were put to the person, so there is nothing unasked to list.
    """
    _, state = read_run(args.run)
    log = state.get("log")
    if any(isinstance(e, dict) and e.get("step") == "ask-deferred"
           for e in (log if isinstance(log, list) else [])):
        return 0
    for path in deferred_questions(state):
        print(f"ITEM: {path}")
        print(f"REASON: {_deferral_reason(path).splitlines()[0].strip()}")
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
    ambiguous = ambiguous_questions(state)
    entity_types = [str(v) for v in listed(state, "entity-types")]
    reprocess = [norm(p) for p in listed(state, "reprocess")]
    keep = [norm(p) for p in listed(state, "continue-low-density")]
    fail = [norm(p) for p in listed(state, "fail-low-density")]
    approved = listed(state, "approved-types")
    declined = listed(state, "declined-types")
    if args.answer == "later":
        if any((reprocess, keep, fail, approved, declined, entity_types)):
            print("`later` leaves every deferral queued; pass no --add with it")
            return 1
        return 0
    problems = []
    if not reprocess:
        problems.append("name each source whose questions were all answered with "
                        "--add reprocess=<management file>")
    low_density = [p for p, step in questions.items() if step == "pass1-extract"]
    for path in reprocess:
        if path not in questions and path not in ambiguous:
            problems.append(f"{path} was not set aside for a question in this run")
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
    problems += _entity_type_problems(ambiguous, entity_types, reprocess, approved)
    if problems:
        print("; ".join(problems))
        return 1
    return 0


def _entity_type_problems(ambiguous: dict[str, list[dict]], values: list[str],
                          reprocess: list[str], approved: list[str]) -> list[str]:
    """The `entity-types` answers name an entity this run left ambiguous, with a type it
    can be written as, and every answered source goes through the passes again."""
    problems, seen = [], set()
    answered_sources = set()
    for value in values:
        parsed = parse_entity_type(value)
        if not parsed:
            problems.append(f"entity-types expects <management file>#<title>=<schema:Type>, "
                            f"got: {value}")
            continue
        path, title, type_name = parsed
        if (path, title) in seen:
            problems.append(f"{path}#{title} is answered more than once")
            continue
        seen.add((path, title))
        if path not in ambiguous:
            problems.append(f"{path} has no ambiguous entity from this run")
            continue
        entity = next((e for e in ambiguous[path] if str(e.get("title")).strip() == title), None)
        if entity is None:
            problems.append(f"{title!r} is not an ambiguous entity of {path}")
            continue
        alternatives = entity.get("alternatives")
        offered = {str(entity.get("type") or "")} | (
            {str(a) for a in alternatives} if isinstance(alternatives, list) else set())
        # A type approved in this same answer has no file yet: Pass 2b writes it only
        # when the source deferred on it goes through again, and nothing orders that
        # source first (or checks the write happened), so the page could be generated
        # from default.md. Such a type waits for the next run.
        if type_name not in offered and not installed_type(type_name):
            if type_name in approved:
                problems.append(f"{type_name} for {title!r} is approved in this answer but has "
                                "no type file yet; give it a candidate or an installed type "
                                "now, or answer it in the next run (and leave its source "
                                "out of reprocess if no other entity of it is answered)")
            else:
                problems.append(f"{type_name} for {title!r} is neither one of its candidates "
                                "nor an installed type")
            continue
        answered_sources.add(path)
        if path not in reprocess:
            problems.append(f"{path} has a type answer but is not in reprocess")
    for path in reprocess:
        if path in ambiguous and path not in answered_sources:
            problems.append(f"{path} is in reprocess but none of its ambiguous entities was "
                            "given a type (add entity-types=<management file>#<title>=<schema:Type>)")
    return problems


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
    # An entity the person gave a type to in `ask-deferred` is written this time round,
    # not left ambiguous again: Pass 2c takes the answer instead of its own doubt.
    if args.run:
        _, state = read_run(args.run)
        item = norm(args.item)
        answered = sorted(title for (p, title) in entity_type_answers(state) if p == item)
        still = {str(e.get("title")).strip() for e in _ambiguous_entities(args.item)}
        left = [t for t in answered if t in still]
        if left:
            print(f"{path}: the person gave a type to {', '.join(map(repr, left))}; write it "
                  "with that type (ambiguous: false in Pass 2c) instead of leaving it in "
                  "ambiguous_entities")
            return 1
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


def page_in_lang_dir(value: str, lang_dir: str) -> str:
    """`value` as a page path under `lang_dir` (`.wikicommit/entity/<lang>/`).

    A merge names its pages the way the person typed them, and `<Type>/<slug>` is
    what `/wikicommit-relate` and WikiLinks use. Compared as typed, that form never
    matched the path the review step logs, and `merge-absorb` was skipped as "not
    ready" — the merge stopped halfway while the run reported success.
    """
    if Path(value).is_file():
        return norm(value)
    if lang_dir:
        candidate = lang_dir + value.removesuffix(".md").strip("/") + ".md"
        if Path(candidate).is_file():
            return candidate
    return value


def lang_dir_of(page: str) -> str:
    m = re.match(r"(\.wikicommit/entity/[^/]+/)", norm(page))
    return m.group(1) if m else ""


def primary_lang_dir() -> str:
    try:
        from _wikilink import load_primary_lang
    except ImportError:
        return ""
    return f".wikicommit/entity/{load_primary_lang()}/"


def merge_pages_of(record: dict, state: dict) -> tuple[str, list[str]]:
    """(kept page, absorbed pages) as repository paths.

    The kept page is the one `choose-pages` added as the run's only candidate — the
    path the agent resolved — or else the argument looked up in `primary_lang`
    (`merge_pages.py plan` refuses a page outside it). The absorbed pages are in the
    kept page's language for the same reason, so they are looked up beside it.
    """
    keep, absorb = merge_arguments(record)
    if not absorb:
        return "", []
    candidates = listed(state, "candidates")
    keep = norm(candidates[0]) if len(candidates) == 1 else page_in_lang_dir(keep, primary_lang_dir())
    lang_dir = lang_dir_of(keep)
    return keep, [page_in_lang_dir(page, lang_dir) for page in absorb]


def cmd_merge_ready(args) -> int:
    """True when this is a merge run and the kept page was rebuilt and written."""
    record, state = read_run(args.run)
    keep, absorb = merge_pages_of(record, state)
    if not absorb:
        print("not a merge run")
        return 1
    for entry in state.get("log", []):
        if (isinstance(entry, dict) and entry.get("step") == "pass4-review"
                and entry.get("outcome") == "rebuilt" and norm(str(entry.get("item", ""))) == keep):
            return 0
    print(f"{keep} was not rebuilt, so nothing is absorbed into it")
    return 1


def cmd_check_merge(args) -> int:
    """The merge was carried through — delegated to merge_pages.py check."""
    record, state = read_run(args.run)
    keep, absorb = merge_pages_of(record, state)
    command = [sys.executable, ".wikicommit/scripts/merge_pages.py", "check", "--into", keep]
    for page in absorb:
        command += ["--absorb", page]
    result = run(command)
    print(result.stdout, end="")
    return 0 if result.returncode == 0 else 1


# Per-page outcomes of `workflow-regenerate.yaml` that leave the page on disk as it was.
NOT_WRITTEN_OUTCOMES = ("skipped", "failed")


def cmd_source_overlap(args) -> int:
    """How much of each page this run wrote repeats its source's wording, for the
    Completion Notice — delegated to check_source_overlap.py.

    The pages are the run's `touched` entity pages (Pass 4's check names every page a
    management file lists). It runs here, after the writes and before the notice,
    because the extracted text Pass 1 kept is certain to be on disk only now. Always
    exit 0: what it prints is a report for a person, never a reason to stop."""
    _, state = read_run(args.run)
    # A --regenerate page the run skipped or whose rebuild failed review is touched
    # too (the engine touches every item that exists), but this run wrote nothing to it.
    log = state.get("log")
    not_written = {norm(str(e["item"])) for e in (log if isinstance(log, list) else [])
                   if isinstance(e, dict) and e.get("item")
                   and e.get("outcome") in NOT_WRITTEN_OUTCOMES}
    pages = [p for p in state.get("touched", [])
             if isinstance(p, str) and p.startswith(".wikicommit/entity/") and Path(p).is_file()
             and norm(p) not in not_written]
    if not pages:
        print("SOURCE_OVERLAP: no page written in this run")
        return 0
    result = run([sys.executable, ".wikicommit/scripts/check_source_overlap.py", *pages])
    print(result.stdout, end="")
    if result.returncode != 0:
        print(f"SOURCE_OVERLAP: check_source_overlap.py could not run (exit {result.returncode})")
    return 0


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
    add("halted-questions", cmd_halted_questions)
    add("has-list", cmd_has_list, list="")
    add("check-answers", cmd_check_answers, answer="")
    add("check-pass1", cmd_check_pass1, run="optional", item=True, outcome=True)
    add("check-pass2b", cmd_check_pass2b, run=False, item=True, outcome=True)
    add("check-pass2c", cmd_check_pass2c, run=False, item=True, outcome=True)
    add("check-pass4", cmd_check_pass4, run="optional", item=True)
    add("check-page-exists", cmd_check_page_exists, run=False, item=True)
    add("merge-ready", cmd_merge_ready)
    add("check-merge", cmd_check_merge)
    add("source-overlap", cmd_source_overlap)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
