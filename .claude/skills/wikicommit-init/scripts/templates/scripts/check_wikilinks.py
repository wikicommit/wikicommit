#!/usr/bin/env python3
"""Check WikiLinks in wiki pages for broken or removed references.

Usage:
    python .wikicommit/scripts/check_wikilinks.py [--changed <path>... [--deleted <path>...]]

With no arguments, every page under .wikicommit/entity/ is checked, matching
validate_frontmatter.py, check_raw_html.py and check_orphans.py. It used to
print "OK: 0 files checked" and exit 0 instead — output a reader cannot tell
from a clean run of a real check (Issue #571). wikicommit-merge always passes
--changed, so the diff-scoped behaviour it relies on is unaffected.

Exit code: 0 = no ERROR (WARNINGs OK), 1 = at least one ERROR.
"""

import argparse
import os
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter_cached
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    VIEW_TYPE_SEGMENT,
    WIKILINK_RE,
    build_slug_type_index,
    collect_entity_pages,
    collect_view_pages,
    other_types_for_slug,
    parse_view_path,
    parse_wiki_path,
)

IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"


def _emit_annotation(level: str, title: str, message: str, file_path: str | None = None) -> None:
    if IN_GITHUB_ACTIONS:
        loc = f"file={file_path}," if file_path else ""
        print(f"::{level} {loc}title={title}::{message}")


def load_primary_lang(repo_root: Path) -> str:
    # Fallback is "en" to match init.py's --primary-lang default (Issue #159 changed the
    # tool-wide default from "ja"; Issue #376 brought this fallback in line with it). Only
    # reached for a config.yml missing/malformed enough to lack an explicit primary_lang —
    # every config.yml init.py generates always has one.
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return "en"
        translation = data.get("translation") or {}
        return str(translation.get("primary_lang", "en") or "en")
    except Exception:
        return "en"


def load_frontmatter(path: Path) -> dict:
    fm, err = parse_frontmatter_cached(path)
    if err:
        print(f"WARNING: {path}: {err}")
        return {}
    return fm


def get_lang(path: Path, primary_lang: str) -> str:
    fm = load_frontmatter(path)
    return str(fm.get("lang", primary_lang))


def is_removed(path: Path) -> bool:
    fm = load_frontmatter(path)
    return fm.get("status") == "removed"


def extract_wikilinks(path: Path) -> list[tuple[str, str]]:
    """Return list of (Type, slug) tuples from [[Type/slug]] in file."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [(m.group(1), m.group(2)) for m in WIKILINK_RE.finditer(content)]


def link_target_path(type_name: str, slug: str, lang: str, entity_dir: Path, view_dir: Path) -> Path:
    """Where `[[<type_name>/<slug>]]` in `lang` would live on disk.

    `View` is a reserved Type segment naming the view tree (Issue #675), whose
    pages have no Type directory: `<view_dir>/<lang>/<slug>.md`. Everything
    else keeps the entity layout. Resolving both here means the existence,
    removed-page and cross-language-fallback checks below stay one code path.
    """
    if type_name == VIEW_TYPE_SEGMENT:
        return view_dir / lang / f"{slug}.md"
    return entity_dir / lang / type_name / f"{slug}.md"


def type_slug_from_wiki_path(
    path: Path, entity_dir: Path, view_dir: Path | None = None
) -> tuple[str, str] | None:
    """Derive (Type, slug) from a page path in either tree.

    Type may contain "/" for nested custom types (e.g. custom/Decision), and is
    the reserved `View` segment for a page in the view tree (Issue #675) — the
    same key a `[[View/<slug>]]` link builds, which is what the backlink index
    this feeds is keyed by.
    """
    resolved = parse_wiki_path(path, entity_dir)
    if resolved is None and view_dir is not None:
        resolved = parse_view_path(path, view_dir)
    if resolved is None:
        return None
    _, type_name, slug = resolved
    return type_name, slug


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check WikiLinks in wiki pages for broken or removed references."
    )
    parser.add_argument("--changed", nargs="+", default=[], metavar="PATH",
                        help="Files being added or modified (default: every page under "
                             ".wikicommit/entity/)")
    parser.add_argument("--deleted", nargs="+", default=[], metavar="PATH",
                        help="Files being marked as status: removed (optional)")
    args = parser.parse_args()

    repo_root = Path.cwd()
    entity_dir = repo_root / ENTITY_DIR
    view_dir = repo_root / VIEW_DIR
    primary_lang = load_primary_lang(repo_root)

    whole_wiki = not args.changed and not args.deleted
    if whole_wiki:
        # Whole-wiki mode. --deleted stays empty on purpose: it means "these
        # files are being marked removed in this change", which only a diff
        # can tell you — there is no such thing outside one. Pages already
        # carrying status: removed are found through --changed as always.
        args.changed = [
            str(page)
            for page in collect_entity_pages(ENTITY_DIR, include_index=True)
            + collect_view_pages(VIEW_DIR, include_index=True)
        ]
        if not args.changed:
            print("OK: 0 files checked, 0 errors, 0 warnings")
            return 0

    changed_paths = [Path(p) for p in args.changed]
    deleted_paths = [Path(p) for p in args.deleted]

    # Resolved absolute paths for --changed (same-commit exception + deleted overlap guard).
    # Empty in whole-wiki mode: the exception below means "the target does not exist yet
    # but this same change adds it", which has no meaning when the set is simply every page
    # already on disk. Leaving it populated made every link resolve through that branch, so
    # a page in one language linking to a page that exists only in <primary_lang> was
    # silently accepted instead of reporting the "translation page not created" WARNING —
    # i.e. the mode could never emit one of the two warnings it exists to surface. Links to
    # status: removed pages are still ERRORs; the ordinary existence path below reports them.
    changed_abs: set[Path] = set() if whole_wiki else {p.resolve() for p in changed_paths}

    total_errors = 0
    total_warnings = 0
    files_checked = 0

    # Built on first use, and only when a link fails to resolve — the common
    # case is an all-green run, which should not pay for a full scan of
    # .wikicommit/entity/ that nothing goes on to read.
    slug_index: dict[str, set[str]] | None = None

    # ── Check WikiLinks in --changed files ────────────────────────────────
    for path in changed_paths:
        if not path.exists():
            print(f"WARNING: {path}: file not found (skipped)")
            total_warnings += 1
            continue

        files_checked += 1

        try:
            rel_str = str(path.relative_to(repo_root))
        except ValueError:
            rel_str = str(path)

        lang = get_lang(path, primary_lang)
        wikilinks = extract_wikilinks(path)

        for type_name, slug in wikilinks:
            lang_path = link_target_path(type_name, slug, lang, entity_dir, view_dir)
            primary_path = link_target_path(type_name, slug, primary_lang, entity_dir, view_dir)

            lang_path_abs = lang_path.resolve()
            primary_path_abs = primary_path.resolve()

            if lang_path_abs in changed_abs or primary_path_abs in changed_abs:
                # Same-commit new addition — but still block links to pages being removed
                target = lang_path if lang_path_abs in changed_abs else primary_path
                if is_removed(target):
                    msg = f"[[{type_name}/{slug}]] → links to a page with status: removed"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                continue

            if lang_path.exists():
                if is_removed(lang_path):
                    msg = f"[[{type_name}/{slug}]] → links to a page with status: removed"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                # else: link is valid
            elif lang != primary_lang and primary_path.exists():
                if is_removed(primary_path):
                    msg = f"[[{type_name}/{slug}]] → links to a page with status: removed"
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation("error", "wikilink-removed", f"{rel_str}: {msg}", rel_str)
                    total_errors += 1
                else:
                    msg = f"[[{type_name}/{slug}]] → exists only in {primary_lang} (translation page not created yet)"
                    print(f"WARNING: {rel_str}: {msg}")
                    _emit_annotation("warning", "wikilink-no-translation", f"{rel_str}: {msg}", rel_str)
                    total_warnings += 1
            else:
                if slug_index is None:
                    # Both roots are passed explicitly: `entity_dir` here is
                    # absolute (repo_root / ENTITY_DIR) while VIEW_DIR, this
                    # parameter's default, is resolved against the process cwd —
                    # so relying on the default would describe two trees that are
                    # only the same repository by coincidence.
                    slug_index = build_slug_type_index(entity_dir, view_dir)
                other_types = other_types_for_slug(type_name, slug, slug_index)

                if other_types:
                    # The page exists; only the Type segment is wrong. Issue #340's
                    # reason for not blocking does not reach this case: the author
                    # cannot dodge the report by leaving the mention as plain text,
                    # because the concept demonstrably already has a page. The fix
                    # is one word, so block and name where the page actually is —
                    # left as a WARNING it reads exactly like the line below, and
                    # check_wanted_pages.py would go on to advise creating a
                    # duplicate of a page that is already there (Issue #563).
                    found = ", ".join(f"{t}/{slug}.md" for t in other_types)
                    msg = (
                        f"[[{type_name}/{slug}]] → this page does not exist, but the "
                        f"same slug exists at {found} (the Type segment may be wrong)"
                    )
                    print(f"ERROR: {rel_str}: {msg}")
                    _emit_annotation(
                        "error", "wikilink-type-mismatch", f"{rel_str}: {msg}", rel_str
                    )
                    total_errors += 1
                else:
                    # Issue #340: downgraded from ERROR to WARNING. Blocking this case
                    # pushed both LLM and human authors toward leaving not-yet-created
                    # concepts as plain text instead of WikiLinks, so recurring concepts
                    # (e.g. benchmark names mentioned across multiple sources) never
                    # accumulated enough signal to get their own page. check_wanted_pages.py
                    # now surfaces these as a non-blocking report instead.
                    msg = f"[[{type_name}/{slug}]] → page does not exist"
                    print(f"WARNING: {rel_str}: {msg}")
                    _emit_annotation("warning", "wikilink-missing", f"{rel_str}: {msg}", rel_str)
                    total_warnings += 1

    # ── Build backlink index once for all --deleted checks ────────────────
    backlink_index: dict[str, list[str]] = {}
    if deleted_paths and entity_dir.exists():
        # collect_entity_pages() matches "assets" below entity_dir, not against
        # the whole path. entity_dir here is absolute (repo_root / ENTITY_DIR),
        # and the old `"assets" in wiki_page.parts` therefore skipped every page
        # in a repository that merely lived under a directory named "assets",
        # leaving this index empty — so the --deleted backlink WARNING, the one
        # thing the removal flow relies on to spot links left dangling, silently
        # stopped being emitted (Issue #677). index.md is kept: rebuild_index.py
        # writes each page's own WikiLink into it, and a link there is a real
        # remaining reference to a page being removed.
        for wiki_page in collect_entity_pages(entity_dir, include_index=True) + collect_view_pages(
            view_dir, include_index=True
        ):
            try:
                content = wiki_page.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                ref_str = str(wiki_page.relative_to(repo_root))
            except ValueError:
                ref_str = str(wiki_page)
            for wl_type, wl_slug in WIKILINK_RE.findall(content):
                key = f"{wl_type}/{wl_slug}"
                refs = backlink_index.setdefault(key, [])
                if ref_str not in refs:
                    refs.append(ref_str)

    # ── Check --deleted files for remaining backlinks ──────────────────────
    for del_path in deleted_paths:
        # If also in --changed (by resolved path), WikiLink check takes priority
        if del_path.resolve() in changed_abs:
            continue

        try:
            del_rel_str = str(del_path.relative_to(repo_root))
        except ValueError:
            del_rel_str = str(del_path)

        # Derive the WikiLink key (Type/slug) from the file path
        resolved = type_slug_from_wiki_path(del_path, entity_dir, view_dir)
        if resolved is None:
            msg = "does not resolve to a path under entity/ or view/, so the backlink check was skipped"
            print(f"WARNING: {del_rel_str}: {msg}")
            _emit_annotation("warning", "wikilink-unresolvable-path", f"{del_rel_str}: {msg}", del_rel_str)
            total_warnings += 1
            continue
        type_name, slug = resolved
        wikilink_key = f"{type_name}/{slug}"

        for ref_str in backlink_index.get(wikilink_key, []):
            msg = f"a backlink remains ({ref_str})"
            print(f"WARNING: {del_rel_str} (being changed to status: removed): {msg}")
            _emit_annotation(
                "warning", "wikilink-backlink-remaining",
                f"{del_rel_str}: {msg}", del_rel_str
            )
            total_warnings += 1

    print(f"OK: {files_checked} files checked, {total_errors} errors, {total_warnings} warnings")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
