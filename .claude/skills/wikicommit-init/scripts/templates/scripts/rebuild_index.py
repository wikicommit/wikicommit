#!/usr/bin/env python3
"""Deterministically rebuild index.md for one or more wiki Type directories.

wikicommit-generate and wikicommit-translate both need to update `index.md`
for every Type directory they touched (`[[Type/slug]] — title` listing, per
`docs/DesignDoc-skills.md` §11.6 / §6.4). Previously this was a step the LLM
agent had to remember to perform "once, after all sources/pairs" at the tail
of a long multi-step run — a purely deterministic, full-directory-scan
operation left to agent memory instead of a script (Issue #406). This script
takes over that step: given a Type directory, it scans the directory on disk
and writes a fresh `index.md` from scratch, so a skipped step in a long batch
can no longer leave a stale or missing index.

Usage:
    python .wikicommit/scripts/rebuild_index.py [<type-dir>...]

- No arguments: rebuild every Type directory found under `.wikicommit/entity/`
  (any directory that directly contains at least one non-index.md page).
- One or more arguments: rebuild only those Type directories, e.g.
  `.wikicommit/entity/ja/Person` or `.wikicommit/entity/en/custom/Decision`.

Exit code: always 0 (this is a workflow step, not a wikicommit-merge quality
gate; a directory that can't be resolved is reported as a WARNING and
skipped rather than failing the whole run).
"""

import argparse
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter
from _wikilink import ENTITY_DIR


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


def discover_type_dirs() -> list[Path]:
    """Find every directory under ENTITY_DIR that directly holds at least one
    non-index.md page, at <lang>/<Type> depth or deeper (nested custom types)."""
    if not ENTITY_DIR.exists():
        return []
    dirs: set[Path] = set()
    for page in ENTITY_DIR.rglob("*.md"):
        if "assets" in page.parts or page.name == "index.md":
            continue
        parent = page.parent
        try:
            rel = parent.relative_to(ENTITY_DIR)
        except ValueError:
            continue
        if len(rel.parts) < 2:
            continue
        dirs.add(parent)
    return sorted(dirs)


def rebuild_index(type_dir: Path) -> tuple[str, int] | None:
    """Rebuild index.md for a single Type directory. Returns (path, page_count),
    or None if the directory was skipped (reported via WARNING)."""
    if not type_dir.is_dir():
        print(f"WARNING: {type_dir}: directory not found, skipped")
        return None

    resolved = _parse_type_dir(type_dir)
    if resolved is None:
        print(f"WARNING: {type_dir}: not a <lang>/<Type> path under {ENTITY_DIR}, skipped")
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
            print(f"WARNING: {page}: title フィールドがありません — omitted from index.md")
            continue
        entries.append((page.stem, str(title)))
    entries.sort(key=lambda e: e[0])

    leaf_title = type_name.rsplit("/", 1)[-1]
    frontmatter = (
        "---\n"
        f"title: {_yaml_quote(leaf_title)}\n"
        f"lang: {lang}\n"
        f'type: {_yaml_quote(f"schema:{type_name}")}\n'
        "---\n"
    )
    body_lines = [f"[[{type_name}/{slug}]] — {title}" for slug, title in entries]
    content = frontmatter + "\n" + ("\n".join(body_lines) + "\n" if body_lines else "")

    index_path = type_dir / "index.md"
    index_path.write_text(content, encoding="utf-8")
    return str(index_path), len(entries)


def collect_target_dirs(args: list[str]) -> list[Path]:
    if args:
        return [Path(p) for p in args]
    return discover_type_dirs()


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
