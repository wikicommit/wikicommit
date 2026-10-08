#!/usr/bin/env python3
"""rename_page.py — qualify a page's name by year, carrying links and translations along.

Editions of one series — a yearly report, a numbered volume — share a name.
`/wikicommit-relate` records them as a `series`, and before it does, each
edition's name is qualified the same way, so a reader can tell them apart:

    slug    <slug>-<year>
    title   <title>（<year>）   in ja / zh
            <title> (<year>)   in every other language

The year is the only qualifier used, because it is the only one every type has
(a report has a number, a conference an edition, a law neither). The rule lives
here rather than in a type template, because it runs across types and an
installed type template is not edited after init.

    plan   --page <page> --year YYYY [--base-title LANG=NAME ...]
        Print what the rename does and write nothing:
            RENAME: <old path> -> <new path>      (once per language)
            TITLE: <lang> "<old>" -> "<new>"
            UNCHANGED: <page> already carries the qualifier
            SUMMARY: pages=<N>, slug_changed=<yes|no>

    apply  --page <page> --year YYYY [--base-title LANG=NAME ...] [--today YYYY-MM-DD]
        Carry it out. The title of the page and of each of its translations gets
        the qualifier. When the slug changes as well, the rename reuses what a
        merge does (`merge_pages.py`): a page at the new slug is written in every
        language, the old one is taken down with `removed_reason: merged` and
        `merged_into` the new one, a `same` item with `merged_into` and
        `renamed_at` is appended to `.wikicommit/relations.yml`, every WikiLink to
        the old slug is rewritten (`rewrite_merged_links.py`), `generated_pages`
        in the source management files is pointed at the new path, and the type
        indexes are rebuilt. Lines printed besides `plan`'s:
            WROTE: <path>
            REMOVED: <path>
            REWRITTEN: <path> (<N> link(s))
            SOURCE_FILE: <path>
            GROUPS: <file> lists <old slug>; change it to <new slug>

`--base-title LANG=NAME` sets the name the qualifier is added to, per language;
the default is the current title, with a qualifier for the same year removed
if it is already there. Use it when an edition's title carries something else
(a report number) that the series' names should not.

Every page whose title changes goes back to `review_status: pending` (and
loses `reviewed_by`): the title is content, and a person's sign-off covers the
text they read. Its translations are left for `/wikicommit-translate` like any
other translation of a changed page. Review records stay where they are: a
record names the page path it judged. `check_review_coverage.py` and the publish
banner follow the `renamed_at` item back to them (Issue #1162); with the title
changed, the verdict reads as `STALE_REVIEW:` until the new page is reviewed.

Refused (exit 1, nothing written) when the page is missing, removed, a
translation, a synthesized page or outside `primary_lang`; when the year is not
four digits; or when the new slug is taken in some language.

Exit code: 0 = done (or nothing to do), 1 = refused.
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

from _wikilink import ENTITY_DIR, load_primary_lang, parse_wiki_path
from merge_pages import Refused, frontmatter, rel, translations_of
from set_frontmatter_field import apply_frontmatter_fields

SOURCE_DIR = Path(".wikicommit/source")
FULL_WIDTH_LANGS = ("ja", "zh")
YEAR_RE = re.compile(r"^\d{4}$")
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def qualifier(lang: str, year: str) -> str:
    return f"（{year}）" if lang.split("-")[0] in FULL_WIDTH_LANGS else f" ({year})"


def qualified_title(title: str, lang: str, year: str, base: str | None = None) -> str:
    name = (base if base is not None else title).strip()
    for suffix in (f"（{year}）", f"({year})"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].rstrip()
    return name + qualifier(lang, year)


def qualified_slug(slug: str, year: str) -> str:
    return slug if slug.endswith(f"-{year}") else f"{slug}-{year}"


def parse_bases(raw: list[str]) -> dict[str, str]:
    bases = {}
    for item in raw:
        lang, sep, name = item.partition("=")
        if not sep or not lang.strip() or not name.strip():
            raise Refused(f"--base-title must be LANG=NAME: {item!r}")
        bases[lang.strip()] = name.strip()
    return bases


def build_plan(page_arg: str, year: str, bases: dict[str, str]) -> dict:
    if not YEAR_RE.match(year):
        raise Refused(f"--year must be four digits: {year!r}")
    page = Path(page_arg)
    if page.is_absolute():
        # Every stored path (translated_from, merged_into, generated_pages) is
        # repository-relative; an absolute --page would match none of them and
        # would write an absolute merged_into.
        page = Path(os.path.relpath(page))
    if not page.is_file():
        raise Refused(f"{rel(page)} does not exist")
    parsed = parse_wiki_path(page, ENTITY_DIR)
    if parsed is None:
        raise Refused(f"{rel(page)} is not a page under {ENTITY_DIR.as_posix()}/<lang>/<Type>/ "
                      "(view pages are not renamed)")
    lang, type_name, slug = parsed
    primary = load_primary_lang()
    if lang != primary:
        raise Refused(f"{rel(page)} is not in primary_lang ({primary}); rename the original page, "
                      "and its translations follow")
    fm = frontmatter(page)
    if fm.get("status") == "removed":
        raise Refused(f"{rel(page)} is at status: removed")
    if fm.get("translated_from"):
        raise Refused(f"{rel(page)} is a translation; rename its original instead")
    if fm.get("derived_from"):
        raise Refused(f"{rel(page)} is a synthesized page; /wikicommit-synthesize owns it")

    new_slug = qualified_slug(slug, year)
    if not SLUG_RE.match(new_slug):
        raise Refused(f"{new_slug!r} is not a valid slug")
    moves = []  # (lang, old path, new path, old title, new title, is translation)
    for target in [page, *[t for t in translations_of(page) if frontmatter(t).get("status") != "removed"]]:
        t_lang = parse_wiki_path(target, ENTITY_DIR)[0]
        old_title = str(frontmatter(target).get("title") or "")
        new_title = qualified_title(old_title, t_lang, year, bases.get(t_lang))
        new_path = target.with_name(f"{new_slug}.md")
        moves.append((t_lang, target, new_path, old_title, new_title, target != page))
    if new_slug != slug:
        for lang_dir in sorted(p for p in ENTITY_DIR.iterdir() if p.is_dir()):
            taken = lang_dir / type_name / f"{new_slug}.md"
            if taken.exists():
                raise Refused(f"{rel(taken)} already exists; choose the qualifier by hand")
    return {
        "page": page,
        "type": type_name,
        "old_id": f"{type_name}/{slug}",
        "new_id": f"{type_name}/{new_slug}",
        "slug": slug,
        "new_slug": new_slug,
        "moves": moves,
    }


def print_plan(plan: dict) -> bool:
    """Print the plan; return whether anything changes."""
    slug_changed = plan["new_slug"] != plan["slug"]
    changed = slug_changed
    for t_lang, old, new, old_title, new_title, _ in plan["moves"]:
        if slug_changed:
            print(f"RENAME: {rel(old)} -> {rel(new)}")
        if old_title != new_title:
            changed = True
            print(f"TITLE: {t_lang} {json.dumps(old_title, ensure_ascii=False)} -> "
                  f"{json.dumps(new_title, ensure_ascii=False)}")
    if not changed:
        print(f"UNCHANGED: {rel(plan['page'])} already carries the qualifier")
    print(f"SUMMARY: pages={len(plan['moves'])}, slug_changed={'yes' if slug_changed else 'no'}")
    return changed


def cmd_plan(args) -> int:
    print_plan(build_plan(args.page, args.year, parse_bases(args.base_title)))
    return 0


def retitle(path: Path, title: str, translated_from: str | None = None) -> None:
    sets = [("title", json.dumps(title, ensure_ascii=False)), ("review_status", "pending")]
    if translated_from is not None:
        sets.append(("translated_from", translated_from))
    apply_frontmatter_fields(path, sets=sets, unsets=["reviewed_by"])


def repoint_source_files(old: str, new: str) -> list[Path]:
    """Point `generated_pages` entries at the renamed page (line-wise, nothing else touched)."""
    changed = []
    if not SOURCE_DIR.is_dir():
        return changed
    # `\r?` keeps a CRLF file's line matching: the file is read with newline=""
    # so its line endings are written back as they were, and `$` stops before `\n`.
    pattern = re.compile(rf"^([ \t]*-[ \t]*['\"]?){re.escape(old)}(['\"]?[ \t]*\r?)$", re.MULTILINE)
    for path in sorted(SOURCE_DIR.rglob("*.md")):
        with path.open(encoding="utf-8", newline="") as f:
            text = f.read()
        new_text = pattern.sub(lambda m: f"{m.group(1)}{new}{m.group(2)}", text)
        if new_text != text:
            with path.open("w", encoding="utf-8", newline="") as f:
                f.write(new_text)
            changed.append(path)
    return changed


def cmd_apply(args) -> int:
    import rebuild_index
    import record_relation
    import rewrite_merged_links
    from _groups import load_group_file

    plan = build_plan(args.page, args.year, parse_bases(args.base_title))
    if not print_plan(plan):
        return 0
    if plan["new_slug"] == plan["slug"]:
        for _, old, _, old_title, new_title, _ in plan["moves"]:
            if old_title != new_title:
                retitle(old, new_title)
                print(f"WROTE: {rel(old)}")
        return 0

    try:
        text = record_relation.existing_text()
        record_relation.append_record({
            "relation": "same",
            "pages": [plan["old_id"], plan["new_id"]],
            "merged_into": plan["new_id"],
            "renamed_at": args.today,
        }, text)
    except (ValueError, OSError) as exc:
        raise Refused(str(exc)) from exc

    new_original = rel(plan["moves"][0][2])
    for _, old, new, old_title, new_title, is_translation in plan["moves"]:
        with old.open(encoding="utf-8", newline="") as f:
            content = f.read()
        with new.open("w", encoding="utf-8", newline="") as f:
            f.write(content)
        # Only a page whose title changes loses its review status, as in the
        # branch above: a slug is a file name, not text a person read. A
        # translation still points at the original's new path.
        if old_title != new_title:
            retitle(new, new_title, new_original if is_translation else None)
        elif is_translation:
            apply_frontmatter_fields(new, sets=[("translated_from", new_original)])
        print(f"WROTE: {rel(new)}")
    for _, old, new, _, _, _ in plan["moves"]:
        apply_frontmatter_fields(old, sets=[
            ("status", "removed"),
            ("removed_at", json.dumps(args.today)),
            ("removed_reason", "merged"),
            ("merged_into", rel(new)),
        ])
        print(f"REMOVED: {rel(old)}")

    rewrite_merged_links.main([])
    for path in repoint_source_files(rel(plan["page"]), new_original):
        print(f"SOURCE_FILE: {rel(path)}")
    for type_dir in sorted({old.parent for _, old, _, _, _, _ in plan["moves"]}):
        rebuild_index.rebuild_index(type_dir)
    group_file, _ = load_group_file(plan["type"])
    if group_file is not None and plan["slug"] in group_file.group_of():
        print(f"GROUPS: {rel(group_file.path)} lists {plan['slug']}; change it to {plan['new_slug']}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Qualify a page's slug and title by year.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("plan", cmd_plan), ("apply", cmd_apply)):
        p = sub.add_parser(name)
        p.add_argument("--page", required=True, help="the original page under .wikicommit/entity/<primary_lang>/")
        p.add_argument("--year", required=True, metavar="YYYY")
        p.add_argument("--base-title", action="append", default=[], metavar="LANG=NAME")
        if name == "apply":
            p.add_argument("--today", default=datetime.date.today().isoformat(), metavar="YYYY-MM-DD")
        p.set_defaults(func=func)
    args = parser.parse_args(argv)
    if getattr(args, "today", None) and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.today):
        print(f"ERROR: --today must be YYYY-MM-DD: {args.today!r}")
        return 1
    try:
        return args.func(args)
    except Refused as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
