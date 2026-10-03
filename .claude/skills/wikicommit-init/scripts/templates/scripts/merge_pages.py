#!/usr/bin/env python3
"""merge_pages.py — what a merge of "same" pages needs, worked out from disk (Issue #1119).

A person who decided with `/wikicommit-relate` that two or more pages are one
concept merges them with

    /wikicommit-generate --regenerate <kept page> --merge <absorbed page> [...]

The body of the merged page is written by the regeneration passes (Pass 1 / 3 / 4,
shared with an ordinary rebuild). What this script does is the part that must not
depend on an agent's reading: which pages take part, which sources the merged page
now rests on, which names it carries over, whether the merge is backed by a
recorded decision, and — once it is done — whether it was carried through.

    plan    --into <page> --absorb <page> [...]
        Check the merge can go ahead and print what it involves:
            KEEP: <path>
            ABSORB: <path>
            TRANSLATION: <path> (of <absorbed path>)
            SOURCE: <type> <identifier> <hash>
            ALIAS: <name>
            SUMMARY: absorb=<N>, translations=<N>, sources=<N>, aliases=<N>
        `ALIAS:` lines are the names the merged page takes over from the absorbed
        pages (their titles and aliases, and their translations' titles). They rest
        on the person's decision, not on a source's wording, so Pass 4 does not
        check them as added aliases, and Pass 3's one-alias-per-language limit does
        not apply to them.

    record  --into <page> --absorb <page> [...] [--today YYYY-MM-DD]
        Append the merge to `.wikicommit/relations.yml` — a `same` item naming the
        pages, with `merged_into` and `merged_aliases`. Run it before the absorbed
        pages are removed (`plan` refuses removed pages).

    check   --into <page> --absorb <page> [...]
        After the merge: the record is there, the kept page carries the merged
        aliases, every absorbed page and its translations is at `status: removed`
        with `merged_into` the kept page, and no live page still links to an
        absorbed one. `TOUCHED:` lines name the files the merge wrote.

The merge is refused (exit 1, nothing written) when a page is missing, removed,
a translation or a synthesized page, outside `primary_lang`, or when no `same`
item in the relations file names the kept page together with each absorbed one.
It is also refused when a source is `type: manual` (it cannot be re-acquired, so
the rebuild would drop what rested on it — the same reason `--regenerate` skips
such pages) or when one source is recorded with two different hashes (one page
was written from an older version of it; bring the source up to date first).

Exit code: 0 = done, 1 = refused or a check failed.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    collect_view_pages,
    load_primary_lang,
    normalize_entity_prefix,
    normalize_name,
    parse_wiki_path,
)

RELATIONS_FILE = Path(".wikicommit/relations.yml")


class Refused(Exception):
    pass


def ident_of(path: Path) -> str:
    parsed = parse_wiki_path(path, ENTITY_DIR)
    if parsed is None:
        raise Refused(f"{path.as_posix()} is not a page under {ENTITY_DIR.as_posix()}/<lang>/<Type>/")
    _, type_name, slug = parsed
    return f"{type_name}/{slug}"


def frontmatter(path: Path) -> dict:
    fm, _ = parse_frontmatter(path)
    return fm if isinstance(fm, dict) else {}


def rel(path: Path) -> str:
    return path.as_posix().removeprefix("./")


def load_relations() -> list:
    if not RELATIONS_FILE.is_file():
        return []
    try:
        data = yaml.safe_load(RELATIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Refused(f"{RELATIONS_FILE.as_posix()} could not be read: {exc}") from exc
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def same_pairs(records: list) -> set[frozenset]:
    pairs = set()
    for record in records:
        if record.get("relation") != "same" or not isinstance(record.get("pages"), list):
            continue
        members = [p for p in record["pages"] if isinstance(p, str)]
        for a in members:
            for b in members:
                if a != b:
                    pairs.add(frozenset((a, b)))
    return pairs


def translations_of(page: Path) -> list[Path]:
    """Pages, in any language and any status, whose `translated_from` is `page`."""
    target = rel(page)
    found = []
    for candidate in collect_entity_pages(ENTITY_DIR):
        stored = frontmatter(candidate).get("translated_from")
        if isinstance(stored, str) and normalize_entity_prefix(stored.strip().replace("\\", "/")) == target:
            found.append(candidate)
    return found


def source_key(entry: dict) -> tuple[str, str] | None:
    kind = entry.get("type")
    if kind in ("url", "wikicommit") and isinstance(entry.get("url"), str):
        return (kind, entry["url"])
    if kind == "path" and isinstance(entry.get("path"), str):
        return (kind, entry["path"])
    if kind == "manual":
        return ("manual", str(entry.get("author", "")))
    return None


def alias_list(value) -> list:
    """`aliases` as a list — a bare string is one alias, not one per character."""
    if isinstance(value, list):
        return value
    return [value] if isinstance(value, str) else []


def merged_aliases(keep_fm: dict, absorbed: list[Path]) -> list[str]:
    """Names the merged page takes over: each absorbed page's title and aliases,
    then its translations' titles — minus the kept page's own title, deduplicated
    on `normalize_name()`, in that order."""
    seen = {normalize_name(str(keep_fm.get("title", "")))}
    names: list[str] = []

    def add(value) -> None:
        if isinstance(value, str) and value.strip():
            key = normalize_name(value)
            if key not in seen:
                seen.add(key)
                names.append(value.strip())

    for page in absorbed:
        fm = frontmatter(page)
        add(fm.get("title"))
        for alias in alias_list(fm.get("aliases")):
            add(alias)
    for page in absorbed:
        for translation in translations_of(page):
            add(frontmatter(translation).get("title"))
    return names


def build_plan(into: str, absorb: list[str], *, live: bool = True) -> dict:
    keep = Path(into)
    absorbed = [Path(a) for a in absorb]
    if not absorbed:
        raise Refused("name at least one page to absorb with --absorb")
    if len({rel(p) for p in [keep, *absorbed]}) != len(absorbed) + 1:
        raise Refused("a page is named twice")
    primary = load_primary_lang()
    for page in [keep, *absorbed]:
        if not page.is_file():
            raise Refused(f"{rel(page)} does not exist")
        parsed = parse_wiki_path(page, ENTITY_DIR)
        if parsed is None:
            raise Refused(f"{rel(page)} is not a page under {ENTITY_DIR.as_posix()}/<lang>/<Type>/ "
                          "(view pages are not merged)")
        if parsed[0] != primary:
            raise Refused(f"{rel(page)} is not in primary_lang ({primary}); merge the original pages, "
                          "and their translations follow")
        fm = frontmatter(page)
        if live and fm.get("status") == "removed":
            raise Refused(f"{rel(page)} is at status: removed")
        if fm.get("translated_from"):
            raise Refused(f"{rel(page)} is a translation; merge its original instead")
        if fm.get("derived_from"):
            raise Refused(f"{rel(page)} is a synthesized page; /wikicommit-synthesize owns it")

    keep_id = ident_of(keep)
    pairs = same_pairs(load_relations())
    for page in absorbed:
        if frozenset((keep_id, ident_of(page))) not in pairs:
            raise Refused(
                f"no `same` item in {RELATIONS_FILE.as_posix()} names {keep_id} together with "
                f"{ident_of(page)}; decide it with /wikicommit-relate first"
            )

    sources: dict[tuple[str, str], str] = {}
    for page in [keep, *absorbed]:
        for entry in frontmatter(page).get("sources") or []:
            if not isinstance(entry, dict):
                continue
            key = source_key(entry)
            if key is None:
                continue
            if key[0] == "manual":
                raise Refused(f"{rel(page)} has a `type: manual` source, which cannot be re-acquired; "
                              "merge such a page by hand")
            digest = str(entry.get("hash", ""))
            if key in sources and sources[key] != digest:
                raise Refused(
                    f"{key[1]} is recorded with two different hashes across the merged pages; one page "
                    f"was written from an older version — run /wikicommit-generate {key[1]} first"
                )
            sources[key] = digest

    keep_fm = frontmatter(keep)
    return {
        "keep": keep,
        "keep_id": keep_id,
        "absorbed": absorbed,
        "absorbed_ids": [ident_of(p) for p in absorbed],
        "translations": [(t, p) for p in absorbed for t in translations_of(p)],
        "sources": sources,
        "aliases": merged_aliases(keep_fm, absorbed),
    }


def cmd_plan(args) -> int:
    plan = build_plan(args.into, args.absorb)
    print(f"KEEP: {rel(plan['keep'])}")
    for page in plan["absorbed"]:
        print(f"ABSORB: {rel(page)}")
    for translation, original in plan["translations"]:
        print(f"TRANSLATION: {rel(translation)} (of {rel(original)})")
    for (kind, identifier), digest in plan["sources"].items():
        print(f"SOURCE: {kind} {identifier} {digest}".rstrip())
    for name in plan["aliases"]:
        print(f"ALIAS: {name}")
    print(
        f"SUMMARY: absorb={len(plan['absorbed'])}, translations={len(plan['translations'])}, "
        f"sources={len(plan['sources'])}, aliases={len(plan['aliases'])}"
    )
    return 0


def cmd_record(args) -> int:
    import record_relation

    plan = build_plan(args.into, args.absorb)
    record = {
        "relation": "same",
        "pages": [plan["keep_id"], *plan["absorbed_ids"]],
        "merged_into": plan["keep_id"],
        "merged_aliases": plan["aliases"],
        "merged_at": args.today,
    }
    try:
        count = record_relation.append_record(record)
    except (ValueError, OSError) as exc:
        raise Refused(str(exc)) from exc
    print(f"RECORDED: {RELATIONS_FILE.as_posix()} (merged {', '.join(plan['absorbed_ids'])} "
          f"into {plan['keep_id']}, aliases={len(plan['aliases'])}, items in file={count})")
    return 0


def merge_record(records: list, keep_id: str, absorbed_ids: list[str]) -> dict | None:
    for record in reversed(records):
        pages = record.get("pages") if isinstance(record.get("pages"), list) else []
        if record.get("merged_into") == keep_id and all(a in pages for a in absorbed_ids):
            return record
    return None


def live_links_to(idents: set[str]) -> list[tuple[str, str]]:
    """(page, Type/slug) for every live page still linking to one of `idents`."""
    found = []
    for page in [*collect_entity_pages(ENTITY_DIR), *collect_view_pages(VIEW_DIR)]:
        if frontmatter(page).get("status") == "removed":
            continue
        text = page.read_text(encoding="utf-8-sig")
        for match in WIKILINK_RE.finditer(text):
            target = f"{match.group(1)}/{match.group(2)}"
            if target in idents:
                found.append((rel(page), target))
    return found


def cmd_check(args) -> int:
    keep = Path(args.into)
    absorbed = [Path(a) for a in args.absorb]
    problems: list[str] = []
    touched: list[str] = []
    if not keep.is_file():
        raise Refused(f"{rel(keep)} does not exist")
    keep_id = ident_of(keep)
    absorbed_ids = [ident_of(p) for p in absorbed]

    record = merge_record(load_relations(), keep_id, absorbed_ids)
    if record is None:
        problems.append(f"{RELATIONS_FILE.as_posix()} has no merge record into {keep_id} "
                        f"covering {', '.join(absorbed_ids)} (merge_pages.py record)")
    else:
        touched.append(RELATIONS_FILE.as_posix())
        have = {normalize_name(a) for a in alias_list(frontmatter(keep).get("aliases")) if isinstance(a, str)}
        missing = [a for a in record.get("merged_aliases") or []
                   if isinstance(a, str) and normalize_name(a) not in have]
        if missing:
            problems.append(f"{rel(keep)} does not carry the merged aliases: {', '.join(missing)}")

    for page in absorbed:
        for target in [page, *translations_of(page)]:
            fm = frontmatter(target)
            stored = str(fm.get("merged_into", "")).strip().replace("\\", "/")
            stored = Path(normalize_entity_prefix(stored)).as_posix() if stored else ""
            if fm.get("status") != "removed" or stored != rel(keep):
                problems.append(f"{rel(target)} is not at status: removed with merged_into: {rel(keep)} "
                                "(remove_page.py --reason merged)")
            else:
                touched.append(rel(target))

    for page, target in live_links_to(set(absorbed_ids)):
        problems.append(f"{page} still links to [[{target}]] (rewrite_merged_links.py)")

    for problem in problems:
        print(problem)
    if problems:
        return 1
    for path in touched:
        print(f"TOUCHED: {path}")
    print(f"OK: {', '.join(absorbed_ids)} merged into {keep_id}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Plan, record and check a merge of same pages.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, func in (("plan", cmd_plan), ("record", cmd_record), ("check", cmd_check)):
        p = sub.add_parser(name)
        p.add_argument("--into", required=True, metavar="PAGE", help="the page that is kept")
        p.add_argument("--absorb", action="append", default=[], metavar="PAGE",
                       help="a page merged into it (repeatable)")
        if name == "record":
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
