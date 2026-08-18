#!/usr/bin/env python3
"""Detect translation status issues: stale, missing-source, and untranslated pages.

Compares each translation page's source_commit against the parent page's
current HEAD commit. Reports STALE when they differ, and MISSING_SOURCE
when the parent page no longer exists. Also walks source pages (pages
without translated_from) and reports UNTRANSLATED for any (page, target
language) pair from .wikicommit/config.yml's translation.targets that has
no corresponding translation page yet.

Usage:
    python .wikicommit/scripts/check_translation_status.py

Exit code: always 0 (warning-only, non-blocking).
"""

import subprocess
import sys
from pathlib import Path

import yaml

from _frontmatter import parse_frontmatter_or_warn as _parse_frontmatter
from _wikilink import ENTITY_DIR, parse_wiki_path, resolve_stored_entity_path


def _git_head_commit(file_path: str) -> tuple[str | None, bool]:
    """Return (commit_hash, ok) for a file.

    Returns (None, False) when git itself fails (e.g. not a git repo).
    Returns ("", True) when git succeeds but the file has no commits yet
    (untracked / newly added), which the caller treats as STALE.

    The pathspec is prefixed with `:(literal)` (Issue #369, same fix as
    Issue #115) — without it, a translated_from path containing glob
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


def collect_translation_pages() -> list[Path]:
    if not ENTITY_DIR.exists():
        return []
    return sorted(p for p in ENTITY_DIR.rglob("*.md") if "assets" not in p.parts)


def load_translation_targets(repo_root: Path = Path(".")) -> list[str]:
    config_path = repo_root / ".wikicommit" / "config.yml"
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return []
        translation = data.get("translation") or {}
        targets = translation.get("targets") or []
        if not isinstance(targets, list):
            return []
        return [str(t) for t in targets]
    except Exception:
        return []


def check_translation_status(targets: list[str]) -> tuple[int, int, int]:
    """Single walk over every wiki page, parsing each page's frontmatter once
    (matching the single-pass convention other _frontmatter.py callers like
    check_orphans.py follow). A page is either a translation (has
    translated_from, checked for STALE/MISSING_SOURCE) or a source page
    (checked for UNTRANSLATED against each configured target), never both."""
    stale_count = 0
    missing_source_count = 0
    untranslated_count = 0

    for page in collect_translation_pages():
        fm = _parse_frontmatter(page)

        translated_from = fm.get("translated_from")
        if translated_from:
            parent_path = resolve_stored_entity_path(str(translated_from))
            if not parent_path.exists():
                print(f"MISSING_SOURCE: {page} (translated_from: {translated_from})")
                print(f"page: {page}")
                missing_source_count += 1
                continue

            source_commit_raw = fm.get("source_commit")
            source_commit = str(source_commit_raw) if source_commit_raw is not None else None
            # Query git log against the resolved (possibly prefix-migrated) path,
            # not the literal translated_from string — a pre-Issue-#477 value
            # still pointing at the old .wikicommit/wiki/ prefix is no longer
            # tracked at that path after the directory rename, so `git log`
            # against it would find only the rename commit itself (or nothing),
            # not the parent page's actual content history.
            parent_head, git_ok = _git_head_commit(str(parent_path))

            if not git_ok:
                print(
                    f"WARNING: {page}: failed to run git log for {translated_from}",
                    file=sys.stderr,
                )
                continue

            if source_commit != parent_head:
                sc_display = str(source_commit) if source_commit is not None else "(none)"
                ph_display = parent_head[:8] if parent_head else "(none)"
                print(
                    f"STALE: {page} (source_commit: {sc_display[:8] if source_commit else sc_display},"
                    f" parent HEAD: {ph_display})"
                )
                print(f"page: {page}")
                stale_count += 1
            continue

        # Source page (no translated_from): check for UNTRANSLATED targets.
        if not targets:
            continue
        if page.name == "index.md":
            continue
        if fm.get("status") == "removed":
            continue

        parsed = parse_wiki_path(page, ENTITY_DIR)
        if parsed is None:
            continue
        lang, type_name, slug = parsed

        for target in targets:
            if target == lang:
                continue
            target_page = ENTITY_DIR / target / type_name / f"{slug}.md"
            if not target_page.exists():
                print(f"UNTRANSLATED: {page} (target: {target})")
                print(f"page: {page}")
                untranslated_count += 1

    return stale_count, missing_source_count, untranslated_count


def main() -> int:
    targets = load_translation_targets()
    stale_count, missing_source_count, untranslated_count = check_translation_status(targets)

    print(
        f"SUMMARY: stale={stale_count}, missing_source={missing_source_count},"
        f" untranslated={untranslated_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
