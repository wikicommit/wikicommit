#!/usr/bin/env python3
"""Deterministically rebuild index.md for one or more wiki Type directories.

wikicommit-generate and wikicommit-translate both need to update `index.md`
for every Type directory they touched (a `[[Type/slug]]` listing).
Previously this was a step the LLM
agent had to remember to perform "once, after all sources/pairs" at the tail
of a long multi-step run — a purely deterministic, full-directory-scan
operation left to agent memory instead of a script (Issue #406). This script
takes over that step: given a Type directory, it scans the directory on disk
and writes a fresh `index.md` from scratch, so a skipped step in a long batch
can no longer leave a stale or missing index.

Usage:
    python .wikicommit/scripts/rebuild_index.py [<type-dir>...]

- No arguments: rebuild every Type directory found under `.wikicommit/entity/`
  (any directory that directly contains at least one page, or an index.md a
  previous run wrote), plus every language directory under `.wikicommit/view/`.
- One or more arguments: rebuild only those directories, e.g.
  `.wikicommit/entity/ja/Person`, `.wikicommit/entity/en/custom/Decision`, or
  `.wikicommit/view/ja`.

A directory under `.wikicommit/view/` is one language's whole view tree, not a
Type directory: view pages carry no type and sit directly under `<lang>/`
(Issue #675), so its index lists `[[View/<slug>]]` and is titled after the
reserved `View` segment rather than after a Type.

Exit code: always 0 (this is a workflow step, not a wikicommit-merge quality
gate; a directory that can't be resolved is reported as a WARNING and
skipped rather than failing the whole run).
"""

import argparse
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    VIEW_TYPE_SEGMENT,
    collect_entity_pages,
    collect_view_pages,
)


def _yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _parse_type_dir(type_dir: Path) -> tuple[str, str] | None:
    """Derive (lang, type_name) from a Type directory path under ENTITY_DIR.

    type_name may contain "/" for nested custom types (e.g. custom/Decision).
    Returns None if the path cannot be resolved under ENTITY_DIR, or has fewer
    than the required <lang>/<type> components.
    """
    try:
        rel = type_dir.resolve().relative_to(ENTITY_DIR.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    parts = rel.parts
    if len(parts) < 2:
        return None
    return parts[0], "/".join(parts[1:])


def _parse_view_lang_dir(lang_dir: Path) -> str | None:
    """Derive `lang` from a `<view>/<lang>` directory, or None if `lang_dir` is
    not exactly one level under the view tree (Issue #675)."""
    try:
        rel = lang_dir.resolve().relative_to(VIEW_DIR.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    parts = rel.parts
    return parts[0] if len(parts) == 1 else None


def discover_view_lang_dirs() -> list[Path]:
    """Every `<view>/<lang>` directory holding at least one page, or an index.md
    a previous run wrote (same reasoning as discover_type_dirs())."""
    dirs: set[Path] = set()
    for page in collect_view_pages(VIEW_DIR, include_index=True):
        parent = page.parent
        if _parse_view_lang_dir(parent) is not None:
            dirs.add(parent)
    return sorted(dirs)


def discover_type_dirs() -> list[Path]:
    """Find every directory under ENTITY_DIR that directly holds at least one
    page, or an index.md this script previously wrote, at <lang>/<Type> depth
    or deeper (nested custom types).

    An existing index.md counts on its own so that a Type directory whose last
    page was removed (`/wikicommit-remove` blanks the entry but leaves the
    index behind) still gets rebuilt: it holds no page for a later
    generate/translate run to rediscover it by, so keying discovery on pages
    alone would strand its index.md at whatever the last rebuild wrote — a
    stale listing, and (Issue #580) frontmatter with no `review_status`, which
    WikiCommitBanner renders as an "unreviewed" warning forever. Rebuilding it
    is exactly what an explicit `rebuild_index.py <that dir>` already does.
    """
    dirs: set[Path] = set()
    # include_index=True: an index.md may be the only .md left in a Type
    # directory (its last page was removed), and that directory still has to be
    # found so its stale index gets rebuilt.
    for page in collect_entity_pages(ENTITY_DIR, include_index=True):
        parent = page.parent
        try:
            rel = parent.relative_to(ENTITY_DIR)
        except ValueError:
            continue
        if len(rel.parts) < 2:
            continue
        dirs.add(parent)
    return sorted(dirs)


def rebuild_view_index(lang_dir: Path, lang: str) -> tuple[str, int]:
    """Rebuild `<view>/<lang>/index.md`, listing that language's view pages
    (Issue #675).

    Same contract as the Type index below — full rescan, deterministic order,
    idempotent — with two differences that follow from a view page having no
    type: entries are `[[View/<slug>]]`, and the frontmatter carries no `type:`
    (validate_frontmatter.py rejects one on a page in this tree).

    Entries are listed flat rather than grouped under `kind` headings. `kind` is
    optional, so any grouping needs a bucket for the pages without one, and a
    heading per kind on a tree that is usually small buys less than the reading
    order it disturbs. Nothing depends on the grouping; it can be added later
    without changing the page's contract.
    """
    entries: list[str] = []
    for page in sorted(lang_dir.glob("*.md")):
        if page.name == "index.md":
            continue
        fm, err = parse_frontmatter(page)
        if err:
            print(f"WARNING: {page}: {err} — omitted from index.md")
            continue
        if (fm or {}).get("status") == "removed":
            continue
        if not (fm or {}).get("title"):
            print(f"WARNING: {page}: has no title field — omitted from index.md")
            continue
        entries.append(page.stem)
    entries.sort()

    frontmatter = (
        "---\n"
        f"title: {_yaml_quote(VIEW_TYPE_SEGMENT)}\n"
        f"lang: {lang}\n"
        "review_status: reviewed\n"
        "comments: false\n"
        "---\n"
    )
    body_lines = [f"- [[{VIEW_TYPE_SEGMENT}/{slug}]]" for slug in entries]
    content = frontmatter + "\n" + ("\n".join(body_lines) + "\n" if body_lines else "")

    index_path = lang_dir / "index.md"
    index_path.write_text(content, encoding="utf-8")
    return str(index_path), len(entries)


def rebuild_index(type_dir: Path) -> tuple[str, int] | None:
    """Rebuild index.md for a single Type directory. Returns (path, page_count),
    or None if the directory was skipped (reported via WARNING)."""
    if not type_dir.is_dir():
        print(f"WARNING: {type_dir}: directory not found, skipped")
        return None

    view_lang = _parse_view_lang_dir(type_dir)
    if view_lang is not None:
        return rebuild_view_index(type_dir, view_lang)

    resolved = _parse_type_dir(type_dir)
    if resolved is None:
        print(
            f"WARNING: {type_dir}: not a <lang>/<Type> path under {ENTITY_DIR} "
            f"nor a <lang> path under {VIEW_DIR}, skipped"
        )
        return None
    lang, type_name = resolved

    entries: list[tuple[str, str]] = []
    for page in sorted(type_dir.glob("*.md")):
        if page.name == "index.md":
            continue
        fm, err = parse_frontmatter(page)
        if err:
            print(f"WARNING: {page}: {err} — omitted from index.md")
            continue
        if (fm or {}).get("status") == "removed":
            continue
        title = (fm or {}).get("title")
        if not title:
            print(f"WARNING: {page}: has no title field — omitted from index.md")
            continue
        entries.append((page.stem, str(title)))
    entries.sort(key=lambda e: e[0])

    leaf_title = type_name.rsplit("/", 1)[-1]
    # review_status: reviewed — same reason as the stamps convert_wikilinks.py
    # already applies in generate_root_index() and _write_source_page() /
    # _write_sources_index() / _write_source_dir_index():
    # this is a build-generated navigation page, not LLM-authored wiki content,
    # so it should not show the wikicommit-banner "unreviewed" warning (which
    # defaults to pending when the field is absent). Issue #580 — a Type index
    # is written here rather than by convert_wikilinks.py and, unlike the root
    # index and the source pages, has a real file under .wikicommit/entity/,
    # which is how it fell outside that convention in the first place. Stamping
    # it at the writing end keeps WikiCommitBanner.tsx free of any "is this an
    # index page?" slug-naming test, which it deliberately avoids.
    #
    # comments: false rides along for the same reason (Issue #741): giscus
    # renders into afterBody on every page, and an index has nothing for a
    # reader to respond to. The plugin skips a page whose frontmatter says so,
    # so this is one key in the place that already decides this question.
    frontmatter = (
        "---\n"
        f"title: {_yaml_quote(leaf_title)}\n"
        f"lang: {lang}\n"
        f'type: {_yaml_quote(f"schema:{type_name}")}\n'
        "review_status: reviewed\n"
        "comments: false\n"
        "---\n"
    )
    # One list item per page, the WikiLink alone (Issue #678). convert_wikilinks.py
    # renders a WikiLink as the *target page's* `title`, so a trailing
    # `— {title}` came out as "Title — Title" on every row of every Type index
    # in every language — and a Type index is one of the wiki's main ways to get
    # around. The suffix was not pointless: read as raw Markdown on GitHub, where
    # `[[...]]` is not rendered, it was the only thing carrying the title. That
    # reader is the operator rather than the audience, the filename beside it
    # already holds the slug, and the cost on the other side falls on every
    # reader on every browse — so the duplication goes.
    #
    # The `- ` marker is load-bearing, not cosmetic. Rows are consecutive
    # non-blank lines, so CommonMark folds them into a single paragraph and
    # Quartz does not turn soft breaks into <br> (quartz.config.yaml ships
    # `hard-line-breaks` disabled). Without a marker the published index is one
    # run-on line of adjacent link texts; the dropped `— {title}` had been
    # separating them by accident. Every other generated listing
    # (generate_root_index() / _write_sources_index() /
    # _write_source_dir_index() / generate_overview_page()) already writes
    # `- [title](link)` for the same reason. remove_page.py's
    # remove_index_entry() tolerates the marker.
    body_lines = [f"- [[{type_name}/{slug}]]" for slug, _title in entries]
    content = frontmatter + "\n" + ("\n".join(body_lines) + "\n" if body_lines else "")

    index_path = type_dir / "index.md"
    index_path.write_text(content, encoding="utf-8")
    return str(index_path), len(entries)


def collect_target_dirs(args: list[str]) -> list[Path]:
    if args:
        return [Path(p) for p in args]
    return discover_type_dirs() + discover_view_lang_dirs()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild index.md for wiki Type directories.")
    parser.add_argument("type_dirs", nargs="*", metavar="<type-dir>")
    parsed = parser.parse_args()

    targets = collect_target_dirs(parsed.type_dirs)

    rebuilt = 0
    for type_dir in targets:
        result = rebuild_index(Path(type_dir))
        if result is not None:
            path, count = result
            print(f"OK: {path} rebuilt ({count} pages)")
            rebuilt += 1

    print(f"SUMMARY: rebuilt={rebuilt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
