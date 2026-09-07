#!/usr/bin/env python3
"""Emit a reduced, whole-wiki view for LLM survey work over .wikicommit/entity/.

Usage:
    python .wikicommit/scripts/build_survey_view.py [--lang <lang>|all] [--max-pages N] [--limit N]

`/wikicommit-synthesize` run with no `<topic>` has to find the topic itself, by
looking at the wiki as a whole (Issue #586). The wiki's full text does not fit
in one context, so this script reduces every page to the few lines that carry
its cross-cutting structure — title, type, tags, `properties.description`,
its `##` section headings, and the WikiLinks it makes — and adds the aggregate
rankings (hubs, tags, types) computed from the link graph.

Why headings and the link graph, and not only `properties.description`:
`description` is capped at two or three sentences by design (Issue #495), so a
pattern that only shows up in a page's body would be invisible in a
description-only digest. Section headings are the cheapest part of a body that
still names what it covers. The graph matters even more: "several Place pages
connect through one Person" is not a statement about any single page's text at
all — it exists only between pages, and only a view that sees all of them at
once can find it.

This is deliberately a script rather than prose in a SKILL.md: surveying the
wiki means walking every page, and partial coverage would silently undercut the
one thing the survey is for. What the script does not do is judge — picking
topics out of this digest is the LLM's job, and is non-deterministic by nature.

Exit code: always 0 (report-only; an unreadable page is a WARNING on stderr).
"""

import argparse
import re
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter_and_body_text
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    WIKILINK_RE,
    collect_entity_pages,
    collect_view_pages,
    parse_view_path,
    parse_wiki_path,
)

# Headings only; a "#" inside a fenced code block is not one, and neither is a
# body-level H1 (pages are not supposed to have one at all — Issue #546).
HEADING_RE = re.compile(r"^#{2,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^(?:```|~~~).*?(?:^(?:```|~~~)\s*$|\Z)", re.MULTILINE | re.DOTALL)

MAX_DESC_CHARS = 160
MAX_HEADINGS = 8


def load_primary_lang(repo_root: Path) -> str:
    """Same fallback as convert_wikilinks.load_primary_lang() (Issue #376)."""
    try:
        data = yaml.safe_load((repo_root / ".wikicommit" / "config.yml").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return "en"
        return str((data.get("translation") or {}).get("primary_lang", "en") or "en")
    except Exception:
        return "en"


def page_headings(body: str) -> list[str]:
    """`##`-and-deeper heading texts, with fenced code blocks removed first so a
    comment line inside an example is not read as a section of the page."""
    return [m.group(1).strip() for m in HEADING_RE.finditer(FENCE_RE.sub("", body))]


def _one_line(text: str, limit: int) -> str:
    """Collapse to a single line, neutralize the field delimiter, and cap the
    length.

    Every record here is one line, so an embedded newline would split it into
    two malformed ones. `PAGE:` records are " | "-delimited, so a `|` inside a
    title or tag would read as the start of another field — the reader is an
    LLM, and a title of "A | B" should not look like two columns.
    """
    collapsed = " ".join(str(text).split()).replace("|", "/")
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def collect(entity_dir: Path, view_dir: Path | None = None) -> list[dict]:
    """One record per page, for every language. Filtering by language happens
    afterwards so the link graph is built from the whole wiki: a page's inbound
    links are language-neutral (a WikiLink carries no lang), so counting only
    one language's outbound links would undercount every hub.

    View pages (Issue #675) are included only when `view_dir` is given, which
    the CLI does only under `--include-view`. This view exists to be read for
    angles worth *writing about*, and a view page is already the write-up of
    one — surveying them proposes analysing the analysis, and the pages the
    angle would actually be grounded in are the entity pages underneath. The
    flag is there because reading the view tree is a legitimate thing to want
    (asking what has already been covered), just not the default question.
    """
    pages = []
    paths = list(collect_entity_pages(entity_dir))
    if view_dir is not None:
        paths += collect_view_pages(view_dir)
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"WARNING: {path}: could not be read: {e}", file=sys.stderr)
            continue
        fm, err, body = parse_frontmatter_and_body_text(content)
        if err or not isinstance(fm, dict):
            print(f"WARNING: {path}: {err or 'frontmatter is not a mapping'}", file=sys.stderr)
            continue
        if fm.get("status") == "removed":
            continue
        resolved = parse_wiki_path(path, entity_dir)
        if resolved is None and view_dir is not None:
            resolved = parse_view_path(path, view_dir)
        if resolved is None:
            continue
        lang, type_name, slug = resolved
        props = fm.get("properties")
        tags = fm.get("tags")
        pages.append({
            "path": path,
            "key": f"{type_name}/{slug}",
            "lang": lang,
            "type": type_name,
            "title": str(fm.get("title") or f"{type_name}/{slug}"),
            "tags": [str(t) for t in tags if isinstance(t, (str, int, float))] if isinstance(tags, list) else [],
            "description": str((props or {}).get("description") or "") if isinstance(props, dict) else "",
            "headings": page_headings(body),
            "links": {f"{t}/{s}" for t, s in WIKILINK_RE.findall(content)},
        })
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a reduced whole-wiki view for LLM survey work.")
    parser.add_argument("--lang", default=None, metavar="LANG",
                        help="Language to list pages for, or 'all' (default: config.yml's primary_lang)")
    parser.add_argument("--max-pages", type=int, default=300, metavar="N",
                        help="Cap on listed pages, most-linked first; 0 for no cap (default: 300)")
    parser.add_argument("--limit", type=int, default=20, metavar="N",
                        help="Entries per ranked list (default: 20)")
    parser.add_argument("--include-view", action="store_true",
                        help="Also survey .wikicommit/view/ (excluded by default: a view "
                             "page is already an analysis of other pages)")
    args = parser.parse_args()

    repo_root = Path.cwd()
    entity_dir = ENTITY_DIR
    pages = collect(entity_dir, VIEW_DIR if args.include_view else None)

    # Backlinks are counted per Type/slug key rather than per page: a WikiLink
    # carries no language, so a page and its translations are one node. A page's
    # own link to itself is not a backlink to itself.
    backlinks: dict[str, set[str]] = {}
    for p in pages:
        for link in p["links"]:
            if link != p["key"]:
                backlinks.setdefault(link, set()).add(p["key"])

    lang = args.lang or load_primary_lang(repo_root)
    listed = pages if lang == "all" else [p for p in pages if p["lang"] == lang]
    # Most-linked first, so that a --max-pages cut keeps the pages carrying the
    # wiki's structure rather than an alphabetical slice of it.
    listed.sort(key=lambda p: (-len(backlinks.get(p["key"], ())), p["key"]))
    truncated = 0
    if args.max_pages > 0 and len(listed) > args.max_pages:
        truncated = len(listed) - args.max_pages
        listed = listed[: args.max_pages]

    type_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    for p in listed:
        type_counts[p["type"]] = type_counts.get(p["type"], 0) + 1
        for tag in p["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    langs = sorted({p["lang"] for p in pages})
    print(f"SURVEY: pages={len(listed)}, types={len(type_counts)}, lang={lang}, all_langs={','.join(langs)}")
    if truncated:
        print(
            f"TRUNCATED: {truncated} more page(s) not listed — this survey is incomplete. "
            "Raise --max-pages, or narrow with --lang."
        )

    for type_name, n in sorted(type_counts.items(), key=lambda e: (-e[1], e[0])):
        print(f"TYPE: {type_name} {n}")

    for p in listed:
        refs = len(backlinks.get(p["key"], ()))
        tags = ",".join(_one_line(t, 40) for t in p["tags"])
        links = ",".join(sorted(p["links"]))
        print(f"PAGE: {p['key']} | {_one_line(p['title'], 80)} | backlinks={refs} | tags={tags} | links={links}")
        if p["description"]:
            print(f"  DESC: {_one_line(p['description'], MAX_DESC_CHARS)}")
        if p["headings"]:
            heads = [_one_line(h, 60) for h in p["headings"][:MAX_HEADINGS]]
            more = len(p["headings"]) - len(heads)
            print("  HEADINGS: " + " / ".join(heads) + (f" (+{more})" if more > 0 else ""))

    listed_keys = {p["key"] for p in listed}
    hubs = sorted(
        ((k, len(v)) for k, v in backlinks.items() if k in listed_keys),
        key=lambda e: (-e[1], e[0]),
    )[: args.limit]
    for key, n in hubs:
        print(f"HUB: {key} {n}")

    for tag, n in sorted(tag_counts.items(), key=lambda e: (-e[1], e[0]))[: args.limit]:
        print(f"TAG: {tag} {n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
