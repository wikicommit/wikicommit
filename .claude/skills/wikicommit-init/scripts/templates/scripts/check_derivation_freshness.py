#!/usr/bin/env python3
"""Detect stale synthesized pages whose derivation sources have been updated.

wikicommit-synthesize pages record their multiple source pages in
`derived_from` (a list of {path, source_commit} entries — the multi-source
analog of translated_from/source_commit). This compares each entry's
source_commit against that source page's current HEAD commit. Reports
STALE when they differ, and MISSING_SOURCE when the source page no longer
exists. A page with multiple stale/missing entries gets one line per entry
(same aggregation pattern as check_expires.py etc. — duplicate `page:`
lines for the same page are expected).

Usage:
    python .wikicommit/scripts/check_derivation_freshness.py

Exit code: always 0 (warning-only, non-blocking).
"""

import subprocess
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_or_warn as _parse_frontmatter
from _wikilink import ENTITY_DIR, resolve_stored_entity_path


def _git_head_commit(file_path: str) -> tuple[str | None, bool]:
    """Return (commit_hash, ok) for a file.

    Returns (None, False) when git itself fails (e.g. not a git repo).
    Returns ("", True) when git succeeds but the file has no commits yet
    (untracked / newly added), which the caller treats as STALE.

    The pathspec is prefixed with `:(literal)` (Issue #369, same fix as
    Issue #115) — without it, a derived_from path containing glob
    metacharacters (`[`, `]`, `*`, `?`) could match an unrelated file
    instead of failing cleanly.
    """
    result = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", f":(literal){file_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None, False
    return result.stdout.strip(), True


def collect_pages() -> list[Path]:
    if not ENTITY_DIR.exists():
        return []
    return sorted(p for p in ENTITY_DIR.rglob("*.md") if "assets" not in p.parts)


def main() -> int:
    stale_count = 0
    missing_source_count = 0

    for page in collect_pages():
        fm = _parse_frontmatter(page)

        derived_from = fm.get("derived_from")
        if not derived_from or not isinstance(derived_from, list):
            continue

        for entry in derived_from:
            if not isinstance(entry, dict):
                continue

            source_path = entry.get("path")
            if not source_path:
                continue

            source_path_obj = resolve_stored_entity_path(str(source_path))
            if not source_path_obj.exists():
                print(f"MISSING_SOURCE: {page} (derived_from: {source_path})")
                print(f"page: {page}")
                missing_source_count += 1
                continue

            source_commit_raw = entry.get("source_commit")
            source_commit = str(source_commit_raw) if source_commit_raw is not None else None
            # Query git log against the resolved (possibly prefix-migrated) path,
            # not the literal derived_from[].path string — see the analogous
            # comment in check_translation_status.py.
            current_head, git_ok = _git_head_commit(str(source_path_obj))

            if not git_ok:
                print(
                    f"WARNING: {page}: failed to run git log for {source_path}",
                    file=sys.stderr,
                )
                continue

            if source_commit != current_head:
                sc_display = str(source_commit) if source_commit is not None else "(none)"
                ch_display = current_head[:8] if current_head else "(none)"
                print(
                    f"STALE: {page} (derived_from: {source_path},"
                    f" source_commit: {sc_display[:8] if source_commit else sc_display},"
                    f" current HEAD: {ch_display})"
                )
                print(f"page: {page}")
                stale_count += 1

    print(f"SUMMARY: stale={stale_count}, missing_source={missing_source_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
