"""Shared WikiLink parsing helpers for check_orphans.py, check_wikilinks.py,
and convert_wikilinks.py (Issue #114).

Previously each script carried its own copy of WIKILINK_RE and its own
path→(Type, slug) conversion function, which had drifted out of sync (e.g.
convert_wikilinks.py's regex was missing the double-slash-rejection fix that
check_orphans.py / check_wikilinks.py picked up in PR #109). Consolidating
here means the three scripts (and their templates/ mirrors) can only drift by
skipping the shared import, not by editing divergent logic in place.
"""

import re
from pathlib import Path

# Type may contain "/" for nested custom types (e.g. custom/Decision). Custom
# type directory names are restricted to the same PascalCase word-character
# set as built-in types (no hyphens) — see docs/DesignDoc-data.md §5.3 — so
# the Type segment character class intentionally excludes "-" (only the slug
# segment allows it). Each nested segment requires 1+ chars so "[[Person//foo]]"
# (double slash) is rejected instead of being parsed as type="Person/".
WIKILINK_RE = re.compile(r"\[\[([A-Za-z][A-Za-z0-9_]*(?:/[A-Za-z0-9_]+)*)/([A-Za-z0-9_-]+)\]\]")

# Was independently redefined as `ENTITY_DIR = Path(".wikicommit/entity")` in
# 9 scripts (plus their templates/ mirrors) before being consolidated here
# (Issue #487, found during Issue #477's code review). Relative to the
# process's cwd, same as before — callers running from the repo root keep
# resolving to .wikicommit/entity/ unchanged.
ENTITY_DIR = Path(".wikicommit/entity")


def parse_wiki_path(path: Path, entity_dir: Path = ENTITY_DIR) -> tuple[str, str, str] | None:
    """Derive (lang, type, slug) from a wiki page path under entity_dir.

    type may contain "/" for nested custom types (e.g. custom/Decision).
    Returns None if path cannot be resolved under entity_dir, or has fewer than
    the required <lang>/<type>/<slug>.md components.
    """
    try:
        rel = path.resolve().relative_to(entity_dir.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    parts = rel.parts
    if len(parts) < 3:
        return None
    lang = parts[0]
    type_name = "/".join(parts[1:-1])
    slug = parts[-1].removesuffix(".md")
    return lang, type_name, slug


# A page written before the Issue #477 .wikicommit/wiki/ -> entity/ rename may
# still carry the old prefix verbatim in a stored path field (translated_from,
# derived_from[].path) — no auto-migration, docs/DesignDoc-data.md §4.3's
# coexistence precedent. normalize_entity_prefix()/resolve_stored_entity_path()
# give every consumer of such a field the same tolerance convert_wikilinks.py's
# normalize_wiki_rel() and WikiCommitSources.tsx's translatedFromToRelativePath()
# already have for generated_pages[]/translated_from, instead of each one
# reinventing (or omitting) the same fallback.
LEGACY_ENTITY_PREFIX = ".wikicommit/wiki/"
ENTITY_PREFIX = ".wikicommit/entity/"


def normalize_entity_prefix(raw_path: str) -> str:
    """Rewrite a stored page path's legacy `.wikicommit/wiki/` prefix to the
    current `.wikicommit/entity/` one, for comparing two such values
    (e.g. matching one page's translated_from against another page's
    freshly-computed path) regardless of which prefix either happens to use.
    Leaves any other value, including an already-current-prefix path,
    unchanged.
    """
    if raw_path.startswith(LEGACY_ENTITY_PREFIX):
        return ENTITY_PREFIX + raw_path[len(LEGACY_ENTITY_PREFIX):]
    return raw_path


def resolve_stored_entity_path(raw_path: str, repo_root: Path = Path(".")) -> Path:
    """Resolve a stored repo-relative page path (translated_from /
    derived_from[].path) against the filesystem, tolerating the same legacy
    prefix normalize_entity_prefix() does. Tries the path exactly as stored
    first — correct for a repository that has not renamed its own
    `.wikicommit/wiki/` directory yet — and only falls back to the
    normalized `.wikicommit/entity/` form if the literal path doesn't exist,
    which is correct for a repository that completed the directory rename
    without also rewriting every page's stored path fields. Returns the
    literal (unmodified) path if neither resolves, so callers report the
    as-written path in error messages.
    """
    literal = repo_root / raw_path
    if literal.exists():
        return literal
    normalized = normalize_entity_prefix(raw_path)
    if normalized != raw_path:
        migrated = repo_root / normalized
        if migrated.exists():
            return migrated
    return literal
