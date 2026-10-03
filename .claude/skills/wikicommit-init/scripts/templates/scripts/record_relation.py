#!/usr/bin/env python3
"""record_relation.py — append one relation a person decided between pages (Issue #1095).

`/wikicommit-relate` asks a person how two or more pages relate and records
the answer in one file, `.wikicommit/relations.yml`, as one more item of a
top-level YAML list:

    - relation: distinct
      pages: [DefinedTerm/agent, DefinedTerm/user-agent]
      decided_at: '2026-10-01'
      note: ...

The vocabulary follows the thesaurus standard (ISO 25964 / SKOS):

    same      — one concept under several names (SKOS prefLabel/altLabel).
                Recorded only; merging the pages is a separate step.
    broader   — `broader` contains each of `pages` (SKOS broader/narrower):
                a kind of it, a part of it, or an instance of it.
    related   — associated, neither the same nor one inside the other.
    distinct  — different, despite a shared or similar name. Kept so the
                collision detector stops raising the same pair (Wikidata's
                "different from" exists for the same reason).
    series    — editions of one series (a yearly report, a numbered volume):
                `pages` in series order, oldest first. The series itself is not
                a page — no source describes it — so it lives only here.

Pages are named `<Type>/<slug>` — the language-neutral identifier WikiLinks
use — so one record covers every translation of a page.

The file is only ever appended to: the new item is written as text after the
existing ones, so a person's comments and edits in the file survive. Before
appending, the file must parse as a list (or be empty); if it does not, nothing
is written — appending to a file a person broke would bury the break.

Exit code: 0 = recorded, 1 = refused (nothing written).
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter

RELATIONS_FILE = Path(".wikicommit/relations.yml")
ENTITY_DIR = Path(".wikicommit/entity")
RELATIONS = ("same", "broader", "related", "distinct", "series")
PAGE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z0-9_]+)*/[A-Za-z0-9_-]+$")
HEADER = """\
# Relations a person decided between pages, one list item each.
# Written by /wikicommit-relate (record_relation.py appends; it never rewrites).
# Pages are <Type>/<slug>, the same in every language.
# relation: same | broader | related | distinct | series
# To revise a decision, edit or delete its item.
"""


def page_exists(ident: str) -> bool:
    """True when some language holds the page and it is not at `status: removed`."""
    if not ENTITY_DIR.is_dir():
        return False
    for lang in ENTITY_DIR.iterdir():
        page = lang / f"{ident}.md"
        if lang.is_dir() and page.is_file():
            fm, _ = parse_frontmatter(page)
            if not (isinstance(fm, dict) and fm.get("status") == "removed"):
                return True
    return False


def build_record(args: argparse.Namespace) -> dict:
    pages = [p.strip() for p in args.pages]
    for ident in pages + ([args.broader] if args.broader else []):
        if not PAGE_ID_RE.match(ident):
            raise ValueError(f"{ident!r} is not a page identifier of the form <Type>/<slug>")
        if not page_exists(ident):
            raise ValueError(f"no page {ident} exists under .wikicommit/entity/ (or it is at status: removed)")
    if len(set(pages)) != len(pages):
        raise ValueError("a page is listed twice")
    if args.relation == "broader":
        if not args.broader:
            raise ValueError("a `broader` relation needs --broader (the containing page)")
        if args.broader in pages:
            raise ValueError("--broader must not also be a --page")
        if not pages:
            raise ValueError("a `broader` relation needs at least one narrower --page")
    else:
        if args.broader:
            raise ValueError("--broader belongs only to a `broader` relation")
        if len(pages) < 2:
            raise ValueError(f"a `{args.relation}` relation needs at least two --page")

    record = {"relation": args.relation}
    if args.broader:
        record["broader"] = args.broader
    record["pages"] = pages
    record["decided_at"] = args.today
    note = args.note
    if args.note_file:
        note = Path(args.note_file).read_text(encoding="utf-8")
    if note and note.strip():
        record["note"] = note.strip()
    return record


def existing_text() -> str:
    """Current file text, or "" — refusing a file that is not a YAML list."""
    if not RELATIONS_FILE.exists():
        return ""
    text = RELATIONS_FILE.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"{RELATIONS_FILE.as_posix()} is not valid YAML; fix it first: {exc}") from exc
    if data is not None and not isinstance(data, list):
        raise ValueError(f"{RELATIONS_FILE.as_posix()} is not a YAML list; fix it first")
    return text


def append_record(record: dict, text: str | None = None) -> int:
    """Append one item to the relations file; return the number of items after.

    `text` is the file's current text as `existing_text()` returned it (read
    here when not given). Raises ValueError, writing nothing, when the file
    cannot take an appended item. `merge_pages.py` appends its merge records
    through this same function, so the file has one writer's rules.
    """
    if text is None:
        text = existing_text()
    if not text:
        text = HEADER
    elif not text.endswith("\n"):
        text += "\n"
    item = yaml.safe_dump([record], sort_keys=False, allow_unicode=True, width=10**6)
    # Check the result before writing: an append is only safe after a block-style
    # list. After a flow-style one (`[]`, `[{...}]`) the combined text no longer
    # parses, and writing it would break the file this script refuses to append to.
    try:
        combined = yaml.safe_load(text + item)
    except yaml.YAMLError:
        combined = None
    before = yaml.safe_load(text) if text.strip() else None
    if not isinstance(combined, list) or len(combined) != len(before or []) + 1:
        raise ValueError(
            f"{RELATIONS_FILE.as_posix()} cannot take an appended item (it is probably "
            "written as a flow-style list such as `[]`); rewrite it as a block list, one `- ` item per line, first"
        )
    RELATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RELATIONS_FILE.write_text(text + item, encoding="utf-8")
    return len(combined)


def main() -> int:
    parser = argparse.ArgumentParser(description="Record a relation a person decided between wiki pages.")
    parser.add_argument("--relation", required=True, choices=RELATIONS)
    parser.add_argument("--page", dest="pages", action="append", default=[], metavar="TYPE/SLUG")
    parser.add_argument("--broader", metavar="TYPE/SLUG", help="the containing page (broader only)")
    parser.add_argument("--note", default="")
    parser.add_argument("--note-file")
    parser.add_argument("--today", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    if args.today is None:
        args.today = datetime.date.today().isoformat()
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", args.today):
        print(f"ERROR: --today must be YYYY-MM-DD: {args.today!r}")
        return 1
    try:
        record = build_record(args)
        text = existing_text()
    except (ValueError, OSError) as exc:
        print(f"ERROR: {exc}")
        return 1

    try:
        count = append_record(record, text)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(
        f"RECORDED: {RELATIONS_FILE.as_posix()} (relation={args.relation}, "
        f"pages={len(record['pages']) + (1 if args.broader else 0)}, items in file={count})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
