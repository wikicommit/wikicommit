#!/usr/bin/env python3
"""workflow_checks.py — the wikicommit-translate knowledge `skill_workflow.py` does not have.

`skill_workflow.py` walks `workflow.yaml` and knows nothing about this Skill. Which pages
need translating, where a translation lands, which frontmatter fields it must
carry and where its review record goes live here, next to the workflow, so the
engine stays the same one `wikicommit-generate` and `wikicommit-merge` use.

Every subcommand runs from the repository root and follows the same contract as
the other Skills' checks:

- **exit 0** means yes (a condition holds, a check passed, a list was produced)
- **exit 1** means no, with the reason on stdout
- `ITEM: <value>` lines are a produced list, `TOUCHED: <path>` lines are files the
  check confirmed the step wrote

One item is one (source page, target language) pair, written `<source page> -> <lang>`.
The translation's own path is derived from it, so a resumed run computes the same
target page without anything held in memory.

These checks confirm consistency, not proof: they catch the step that was
forgotten (a page not written, a `source_commit` not written back, a review not
recorded), not one that was faked.
"""

import argparse
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
    import _workflow_checks as shared
    from _workflow_checks import (
        cmd_select, git, read_run, review_records_since, run, run_started, written_since,
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
TREES = (".wikicommit/entity/", ".wikicommit/view/")
STATUS_SCRIPT = Path(".wikicommit/scripts/check_translation_status.py")
STAGE = "translate-check"
GLOSSARY_TYPE = "DefinedTerm"
PAIR_SEP = " -> "
# A `translated_from` still on the pre-rename prefix names the page now under
# `.wikicommit/entity/` (check_translation_status.py resolves it the same way).
LEGACY_ENTITY_PREFIX = ".wikicommit/wiki/"
ENTITY_PREFIX = ".wikicommit/entity/"


def read_markdown(path: Path) -> dict:
    """Frontmatter of a Markdown file; `{}` when there is none or it cannot be read."""
    return shared.read_markdown(path)[0]


def run_arguments(record: dict) -> tuple[str, str]:
    """(page, --lang value) from the arguments the run was started with."""
    args = record.get("args")
    values = [str(a) for a in args] if isinstance(args, list) else []
    page, lang = "", ""
    i = 0
    while i < len(values):
        value = values[i]
        if value == "--lang" and i + 1 < len(values):
            lang = values[i + 1]
            i += 2
            continue
        if value.startswith("--lang="):
            lang = value.split("=", 1)[1]
        elif not value.startswith("--") and not page:
            page = norm(value)
        i += 1
    return page, lang


def norm(path: str) -> str:
    """Repository-relative POSIX path, with a legacy `.wikicommit/wiki/` prefix
    resolved to `.wikicommit/entity/`."""
    posix = shared.norm(path)
    if posix.startswith(LEGACY_ENTITY_PREFIX):
        posix = ENTITY_PREFIX + posix[len(LEGACY_ENTITY_PREFIX):]
    return posix


def config_targets() -> list[str]:
    data = read_yaml(CONFIG)
    translation = data.get("translation") if isinstance(data.get("translation"), dict) else {}
    targets = translation.get("targets") or []
    return [str(t) for t in targets] if isinstance(targets, list) else []


def read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def page_lang(page: str) -> str:
    """The page's `lang`, or the language segment of its path."""
    lang = read_markdown(Path(page)).get("lang")
    if lang:
        return str(lang)
    parts = Path(page).parts
    return parts[2] if len(parts) > 2 else ""


def target_page(source: str, lang: str) -> str:
    """`.wikicommit/<tree>/<lang>/...` with the language segment replaced.

    Entity pages keep their `<Type>/` segment and view pages have none; replacing
    only the language segment is the rule `check_translation_status.py` applies
    to both.
    """
    parts = list(Path(norm(source)).parts)
    if len(parts) < 4:
        return ""
    parts[2] = lang
    return Path(*parts).as_posix()


def split_item(item: str) -> tuple[str, str]:
    source, sep, lang = item.rpartition(PAIR_SEP)
    if not sep or not source or not lang:
        raise ValueError(f"{item!r} is not a `<source page>{PAIR_SEP}<lang>` pair")
    return source.strip(), lang.strip()


def is_glossary(page: str) -> bool:
    parts = Path(norm(page)).parts
    return len(parts) > 4 and parts[1] == "entity" and parts[3] == GLOSSARY_TYPE


# --- preflight ----------------------------------------------------------------


def cmd_preflight(args) -> int:
    """Stop before anything is translated when the run could never finish."""
    if not CONFIG.is_file():
        print(".wikicommit/config.yml does not exist; run /wikicommit-init first")
        return 1
    if not RULES.is_file():
        print(".wikicommit/review-rules.md does not exist; run /wikicommit-init "
              "--no-overwrite to install it (the translate-check review cannot run without it)")
        return 1
    record, _ = read_run(args.run)
    page, lang = run_arguments(record)
    if not page:
        # Batch mode narrows to `--lang`. check_translation_status.py reports
        # UNTRANSLATED only for the configured targets, but STALE for every
        # existing translation: a language outside the targets with no
        # translations on disk would always collect nothing, so say why instead
        # of finishing with "0 pairs". One that has translations (made in
        # single-page mode, or from a target since removed) can still be STALE.
        if lang and lang not in config_targets() and \
                not any(Path(tree, lang).is_dir() for tree in TREES):
            print(f"{lang} is not in `targets` in config.yml and has no translations, so batch "
                  f"mode finds nothing to translate into it. Name a page (`/wikicommit-translate <page> "
                  f"--lang {lang}`), or add {lang} to `targets`.")
            return 1
        return 0
    if not page.startswith(TREES) or not page.endswith(".md"):
        print(f"{page}: not a wiki page under .wikicommit/entity/ or .wikicommit/view/")
        return 1
    if not Path(page).is_file():
        print(f"{page}: the page does not exist")
        return 1
    parent = read_markdown(Path(page)).get("translated_from")
    if parent:
        print(f"{page} is itself a translation (translated_from: {parent}); "
              f"run /wikicommit-translate on {parent} instead")
        return 1
    if not lang and not config_targets():
        print("No target language. Pass `--lang <lang>`, or set `targets` in `config.yml`.")
        return 1
    return 0


# --- conditions and lists -----------------------------------------------------


def cmd_over_cap(args) -> int:
    """Only batch mode asks: a single page's targets are what the person named."""
    record, _ = read_run(args.run)
    page, _ = run_arguments(record)
    if page:
        print("single-page mode; nothing to ask")
        return 1
    return shared.cmd_over_cap(args, noun="pair")


def single_page_pairs(page: str, lang: str) -> list[str]:
    targets = [lang] if lang else config_targets()
    own = page_lang(page)
    pairs = []
    for target in targets:
        if target == own:
            print(f"NOTE: {page} is already in {target}; skipped")
            continue
        pairs.append(f"{norm(page)}{PAIR_SEP}{target}")
    return pairs


def batch_pairs() -> list[str] | None:
    result = run([sys.executable, str(STATUS_SCRIPT)])
    if result.returncode != 0:
        print(f"{STATUS_SCRIPT} exited {result.returncode}: "
              f"{(result.stderr or result.stdout).strip()}")
        return None
    found: list[tuple[str, str, str]] = []  # (reported page, source page, lang)
    for line in result.stdout.splitlines():
        if line.startswith("UNTRANSLATED: "):
            rest = line[len("UNTRANSLATED: "):]
            page, sep, tail = rest.rpartition(" (target: ")
            if sep and tail.endswith(")"):
                found.append((page, page, tail[:-1]))
        elif line.startswith("STALE: "):
            rest = line[len("STALE: "):]
            page = rest.split(" (source_commit:", 1)[0]
            front = read_markdown(Path(page))
            parent, lang = front.get("translated_from"), front.get("lang")
            if parent and lang:
                found.append((page, norm(str(parent)), str(lang)))
            else:
                print(f"NOTE: {page} is STALE but its translated_from or lang cannot be read; skipped")
    # Glossary first, then ascending by the path the status script reported, so a
    # batch settles the target-language terms before the pages that cite them.
    found.sort(key=lambda f: (0 if is_glossary(f[1]) else 1, f[0]))
    pairs: list[str] = []
    for _, source, lang in found:
        pair = f"{norm(source)}{PAIR_SEP}{lang}"
        if pair not in pairs:
            pairs.append(pair)
    return pairs


def cmd_collect(args) -> int:
    """The (source page, target language) pairs this run would translate, in order."""
    record, _ = read_run(args.run)
    page, lang = run_arguments(record)
    pairs = single_page_pairs(page, lang) if page else batch_pairs()
    if pairs is None:
        return 1
    if not page and lang:
        # Narrowing keeps batch_pairs()'s order (glossary first, then reported path).
        pairs = [pair for pair in pairs if split_item(pair)[1] == lang]
    for pair in pairs:
        print(f"ITEM: {pair}")
    return 0


# --- step checks --------------------------------------------------------------


def expected_source_commit(source: str) -> str:
    """What step 4 is told to write: "" when the source page has uncommitted
    changes or no commit, otherwise its last commit."""
    # `:(literal)` so a path with glob metacharacters names only itself — the
    # same pathspec check_translation_status.py uses for the same comparison.
    spec = f":(literal){source}"
    status = git("status", "--porcelain", "--", spec)
    if status.returncode != 0 or status.stdout.strip():
        return ""
    log = git("log", "-1", "--format=%H", "--", spec)
    return log.stdout.strip() if log.returncode == 0 else ""


def cmd_check_pair(args) -> int:
    """The pair's outcome is on disk: a written translation with its write-back
    fields and a passing review record, or a discarded review record and no write."""
    try:
        source, lang = split_item(args.item)
    except ValueError as e:
        print(e)
        return 1
    record, _ = read_run(args.run)
    page = target_page(source, lang)
    if not page:
        print(f"{source}: cannot derive the translation's path")
        return 1
    started = run_started(record)
    if started is None:
        # Without the run's start, a pass record from an earlier run would
        # complete this pair; fail rather than accept every record on disk.
        print(f"{page}: the run record's started_at ({record.get('started_at')!r}) cannot be "
              "read, so this run's review records cannot be told from earlier ones "
              "(the run record is damaged; start a new run)")
        return 1
    wanted = "pass" if args.outcome == "translated" else "discarded"
    matching = [p for p, _ in review_records_since(norm(page), started, STAGE, wanted)]
    if not matching:
        print(f"{page}: no {STAGE} review record with result: {wanted} was written in this run "
              "(record the verdict with record_review.py)")
        return 1

    if args.outcome == "discarded":
        # Nothing is written for a discarded pair: a translation page changed
        # since the run started would be an unreviewed write the run does not own.
        if written_since(Path(page), started):
            print(f"{page}: written during this run, but a discarded pair writes nothing "
                  "(restore the previous translation, or remove a new one)")
            return 1
        print(f"TOUCHED: {matching[-1].as_posix()}")
        return 0

    if not Path(page).is_file():
        print(f"{page}: the translation was not written")
        return 1
    front = read_markdown(Path(page))
    problems = []
    if norm(str(front.get("translated_from") or "")) != norm(source):
        problems.append(f"translated_from is {front.get('translated_from')!r}, not {source!r}")
    if str(front.get("lang") or "") != lang:
        problems.append(f"lang is {front.get('lang')!r}, not {lang!r}")
    if "source_commit" not in front:
        problems.append("source_commit is not written")
    else:
        written = front.get("source_commit")
        written = "" if written is None else str(written)
        expected = expected_source_commit(source)
        if written != expected:
            problems.append(
                f"source_commit is {written!r}, but the source page's is {expected!r}"
                + (" (it has uncommitted changes or no commit, so write the empty string)"
                   if not expected else "")
            )
    if str(front.get("review_status") or "") != "pending":
        problems.append("review_status is not pending")
    if not front.get("translated_by"):
        problems.append("translated_by is not written")
    if not front.get("translated_at"):
        problems.append("translated_at is not written")
    if problems:
        print(f"{page}: " + "; ".join(problems))
        return 1
    print(f"TOUCHED: {page}")
    print(f"TOUCHED: {matching[-1].as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="wikicommit-translate workflow checks")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, item=False, outcome=False, **extra):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True)
        if item:
            p.add_argument("--item", required=True)
        if outcome:
            p.add_argument("--outcome", default="")
        for flag, default in extra.items():
            p.add_argument(f"--{flag.replace('_', '-')}", default=default)
        p.set_defaults(func=func)

    add("preflight", cmd_preflight)
    add("over-cap", cmd_over_cap, list="candidates")
    add("collect", cmd_collect)
    add("select", cmd_select, list="candidates", answer_step="batch-cap")
    add("check-pair", cmd_check_pair, item=True, outcome=True)
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
