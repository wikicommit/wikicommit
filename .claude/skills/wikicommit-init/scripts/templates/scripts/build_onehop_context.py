#!/usr/bin/env python3
"""Assemble the one-hop neighbourhood of a page for Pass 4's check 8.

Usage:
    python .wikicommit/scripts/build_onehop_context.py --page-path <path> < <page body>

Prints one `PAGE:` line per neighbouring page, outbound first, then a single
`SUMMARY:` line. Exit code is always 0 — an empty neighbourhood is a normal
result (a genuinely new, isolated page), not a failure.

Why this is a script at all (Issue #947). Pass 4's check 8 needs "the existing
pages this page links to, plus the pages that link to it", and
`references/pass4-review.md` used to describe how to find them in prose — with
a concrete recipe for the inbound half and nothing at all for the outbound
half. In one pilot run that gap was filled by a throwaway regex,
`\\[\\[([A-Za-z0-9_/]+)\\]\\]`, whose character class has no `-`. WikiCommit
slugs are English kebab-case by Issue #193's rule, so that pattern never
reached the closing `]]` for `vibe-coding` or `spec-driven-development` and
matched none of them. Nothing raised an error: the set simply came back
smaller, and the output looked right. Recomputing it afterwards changed the
context for 24 of 27 pages.

`WIKILINK_RE` in `_wikilink.py` has always had this right — it gives the Type
segment and the slug segment separate character classes, and says why in a
comment — and four scripts already extract links with it. Issue #474's rule
applies exactly: an operation that is fully deterministic should not be
re-derived from prose on each run.

Delegating the whole assembly, rather than only the extraction, also makes the
three skip rules and the cap deterministic. Each of those narrows the set too,
so each could go wrong in the same quiet way.
"""

import argparse
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_cached
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    collect_entity_pages,
    collect_view_pages,
    extract_wikilinks,
    is_removed,
    load_primary_lang,
    normalize_entity_prefix,
    parse_view_path,
    parse_wiki_path,
    resolve_wikilink,
)

# The same order of magnitude wikicommit-ask uses for its own one-hop expansion
# (Issue #459). Applied after the outbound-first dedup, so a page reachable both
# ways spends one slot rather than two.
MAX_PAGES = 5


def page_identity(
    page_path: Path, repo_root: Path, entity_dir: Path, view_dir: Path
) -> tuple[str, str, str] | None:
    """(lang, Type, slug) for the page under review, from its path alone.

    The path is an identifier here, not a file to open: at Pass 4 the page has
    not been written yet for `action: create`, and still holds its previous
    version on disk for `action: update` (`references/pass3-generate.md` item 6
    defers the write to Pass 4 step 6). Reading it would return the outbound
    links of a version that is not the one under review — the same "quietly
    different set" this script exists to remove, rebuilt one layer down.
    """
    absolute = page_path if page_path.is_absolute() else repo_root / page_path
    resolved = parse_wiki_path(absolute, entity_dir)
    if resolved is None:
        resolved = parse_view_path(absolute, view_dir)
    return resolved


def outbound_targets(
    body: str,
    lang: str,
    primary_lang: str,
    entity_dir: Path,
    view_dir: Path,
) -> list[Path]:
    """Existing pages this page links to, in order of appearance, deduplicated.

    Resolution follows the cross-language fallback (own language, then
    `primary_lang`), which is what `resolve_wikilink()` implements. A link that resolves nowhere is dropped
    without comment: pointing at a page nobody has written yet is normal and
    non-blocking (Issue #340), and `check_wanted_pages.py` is what reports it.
    """
    targets: list[Path] = []
    seen: set[Path] = set()
    for type_name, slug in extract_wikilinks(body):
        target = resolve_wikilink(
            type_name, slug, lang, primary_lang, entity_dir, view_dir
        )
        if target is None:
            continue
        key = target.resolve()
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def inbound_pages(
    type_name: str,
    slug: str,
    entity_dir: Path,
    view_dir: Path,
) -> list[Path]:
    """Pages whose body contains `[[<type_name>/<slug>]]`, sorted by path.

    Walks both trees with the shared collectors rather than grepping, so the
    match uses the same `WIKILINK_RE` the outbound half does. Index pages are
    walked (`include_index=True`) so that the skip below can name them: leaving
    them out of the walk and leaving them out by rule produce the same set, but
    only the second can report `skipped`.
    """
    key = (type_name, slug)
    hits: list[Path] = []
    pages = collect_entity_pages(entity_dir, include_index=True) + collect_view_pages(
        view_dir, include_index=True
    )
    for page in pages:
        try:
            content = page.read_text(encoding="utf-8")
        except OSError:
            continue
        if key in extract_wikilinks(content):
            hits.append(page)
    return hits


def translates(page: Path, page_under_review: str) -> bool:
    """Whether `page`'s `translated_from` names the page under review.

    Compared through `normalize_entity_prefix()` because a translation written
    before Issue #477's `.wikicommit/wiki/` → `entity/` rename still carries the
    old prefix verbatim (the two forms are allowed to coexist rather than being
    auto-migrated). A raw string comparison would let such a page through as a
    neighbour, and a disagreement with one's own translation is translation
    staleness — which `check_translation_status.py` already reports as `STALE`.
    """
    fm, err = parse_frontmatter_cached(page)
    if err or not isinstance(fm, dict):
        return False
    translated_from = fm.get("translated_from")
    if not isinstance(translated_from, str) or not translated_from.strip():
        return False
    stored = normalize_entity_prefix(translated_from.strip().replace("\\", "/"))
    return stored == normalize_entity_prefix(page_under_review)


def should_skip(page: Path, page_under_review: str) -> bool:
    """The three skip rules, in the order `references/pass4-review.md` gave them.

    - `index.md`: `rebuild_index.py` writes every page's own WikiLink into its
      Type index, so the inbound half always hits it, and it states no facts of
      its own to contradict anything.
    - `status: removed`: not published, so it cannot disagree with a live page
      in any way a reader would see.
    - a translation of the page under review: see `translates()`.
    """
    if page.name == "index.md":
        return True
    if is_removed(page):
        return True
    return translates(page, page_under_review)


def rel_to_root(page: Path, repo_root: Path) -> str:
    try:
        return str(page.resolve().relative_to(repo_root.resolve()))
    except (ValueError, OSError, RuntimeError):
        return str(page)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble the one-hop page set for Pass 4's cross-page check."
    )
    parser.add_argument(
        "--page-path",
        required=True,
        help="Repo-relative path the page under review has (or will have). Used "
             "only to identify lang/Type/slug — the file itself is never read.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Repository root (default: cwd)."
    )
    parser.add_argument(
        "--max-pages", type=int, default=MAX_PAGES,
        help=f"Cap on the combined set (default: {MAX_PAGES}).",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    entity_dir = repo_root / ENTITY_DIR
    view_dir = repo_root / VIEW_DIR
    primary_lang = load_primary_lang(repo_root)

    page_path = Path(args.page_path.strip())
    identity = page_identity(page_path, repo_root, entity_dir, view_dir)
    if identity is None:
        print(
            f"ERROR: {args.page_path.strip()}: does not resolve to a page under "
            f"{ENTITY_DIR}/ or {VIEW_DIR}/",
            file=sys.stderr,
        )
        return 1
    lang, type_name, slug = identity

    body = sys.stdin.read()
    # The page body arrives on stdin, never as an argument: it is free-form text
    # and long, the same reasoning resolve_source_cache_path.py applies to the
    # identifiers it reads.
    page_rel = rel_to_root(
        page_path if page_path.is_absolute() else repo_root / page_path, repo_root
    )

    ordered: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    # Pages, not hits: one page reachable both ways, or skipped on both passes,
    # is one page. Counting hits would report a `skipped` larger than the number
    # of pages left out, which is the kind of number that stops being read.
    skipped_pages: set[Path] = set()
    self_key = (repo_root / page_rel).resolve()

    # Outbound first: the cap below keeps what comes earlier, and what this page
    # claims to rest on says more about it than what happens to cite it.
    candidates = [
        ("outbound", target)
        for target in outbound_targets(body, lang, primary_lang, entity_dir, view_dir)
    ] + [
        ("inbound", source)
        for source in inbound_pages(type_name, slug, entity_dir, view_dir)
    ]

    for direction, page in candidates:
        key = page.resolve()
        if key == self_key:
            continue
        if key in seen or key in skipped_pages:
            # Already settled on the outbound pass — either kept (in which case
            # it stays reported as outbound) or skipped.
            continue
        if should_skip(page, page_rel):
            skipped_pages.add(key)
            continue
        seen.add(key)
        ordered.append((direction, page))

    # Clamp rather than slice with a negative bound: `ordered[:-1]` would quietly
    # drop the last neighbour and still report a cap, which is the same silent
    # shrink this script exists to remove.
    max_pages = max(0, args.max_pages)
    capped = len(ordered) > max_pages
    kept = ordered[:max_pages]

    outbound_kept = 0
    inbound_kept = 0
    for direction, page in kept:
        if direction == "outbound":
            outbound_kept += 1
        else:
            inbound_kept += 1
        print(f"PAGE: {rel_to_root(page, repo_root)} ({direction})")

    # Always printed, including for an empty set. Without it, "the neighbourhood
    # is empty" and "the extraction returned nothing" look identical — the exact
    # silent shrink this script exists to remove, rebuilt at the new boundary.
    # `skipped` and `capped` are here for the same reason: both narrow the set,
    # so both have to show when they did.
    print(
        f"SUMMARY: outbound={outbound_kept}, inbound={inbound_kept}, "
        f"skipped={len(skipped_pages)}, capped={'true' if capped else 'false'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
