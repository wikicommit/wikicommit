"""Shared WikiLink parsing helpers for check_orphans.py, check_wikilinks.py,
and convert_wikilinks.py (Issue #114).

Previously each script carried its own copy of WIKILINK_RE and its own
path→(Type, slug) conversion function, which had drifted out of sync (e.g.
convert_wikilinks.py's regex was missing the double-slash-rejection fix that
check_orphans.py / check_wikilinks.py picked up in PR #109). Consolidating
here means the three scripts (and their templates/ mirrors) can only drift by
skipping the shared import, not by editing divergent logic in place.

Sibling-imports _frontmatter (build_slug_type_index needs each page's status:),
so anything loading this module — including a test that exec_module()s it
directly — must have the scripts directory on sys.path first. Every script that
imports it lives in that same directory, so this holds at runtime by default.
"""

import re
import unicodedata
from pathlib import Path

from _frontmatter import parse_frontmatter_cached

# Type may contain "/" for nested custom types (e.g. custom/Decision). Custom
# type directory names are restricted to the same PascalCase word-character
# set as built-in types (no hyphens), so
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

# The view tree (Issue #675) holds second-order pages: ones grounded in this
# wiki's own pages (`derived_from`) rather than in an external document
# (`sources` + hash). `/wikicommit-synthesize` writes here.
#
# Its layout deliberately has **no Type segment** — `<lang>/<slug>.md`, not
# `<lang>/<Type>/<slug>.md`. A view page carries no `type:` at all: Schema.org
# is a vocabulary for modelling things, and what separates these pages is not
# their subject but what they can be checked against. Making them pick a type
# anyway is what produced Issue #545, where two runs on one topic resolved to
# `custom/Practice/…` and `Practice/…` and one of them was reachable by no
# WikiLink at all.
VIEW_DIR = Path(".wikicommit/view")

# `View` is a reserved Type segment: `[[View/<slug>]]` in a WikiLink, and
# `content/<lang>/View/<slug>.md` once published. WIKILINK_RE needs no change —
# `View` already matches its Type character class — so this is a resolution-side
# namespace, not a syntax change. Schema.org has no `View` type, so it cannot
# collide with an installed one.
VIEW_TYPE_SEGMENT = "View"

# What a view page *does* with several pages at once, as opposed to what it is
# about. Optional: a page may carry no kind, and pages accumulating without one
# is the evidence that a kind is missing (Issue #553's rule against shipping an
# empty slot — here the slot earns itself). `lineage` (chains of cause and
# derivation) and `process` (a procedure running across pages) are held back
# because neither violates an existing kind's Boundary, which is the bar for
# adding one.
VIEW_KINDS = ("comparison", "debate", "landscape", "pattern", "practice", "timeline")


def normalize_name(value: str) -> str:
    """Fold a page name for comparison — NFKC, case, and runs of whitespace.

    Shared by check_recurring_characters.py (Issue #560) and
    check_unlinked_entity_mentions.py (Issue #561), which between them split
    one question — is this plain-text `properties:` value a page that exists?
    — into two mutually exclusive findings: "no page anywhere, promote it"
    (RECURRING) and "a page exists, link it" (UNLINKED). That split is only
    exhaustive while both scripts fold names the same way, so the folding
    lives here rather than in a copy per script — the same reason this module
    exists at all (see the module docstring).

    check_orphans.py's normalize_title() is deliberately left alone: it does
    the same NFKC + whitespace collapse but folds with `.lower()` rather than
    `.casefold()`, and it only ever compares page titles against each other,
    so it shares no comparison with either caller here.
    """
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


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
# derived_from[].path) — old and new forms are allowed to coexist rather than
# being auto-migrated. normalize_entity_prefix()/resolve_stored_entity_path()
# give every consumer of such a field the same tolerance convert_wikilinks.py's
# normalize_wiki_rel() and WikiCommitSources.tsx's entityPathToRelativePath()
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


def is_entity_asset(page: Path, entity_dir: Path = ENTITY_DIR) -> bool:
    """Whether `page` lives under `entity_dir`'s single top-level `assets/`.

    `.wikicommit/entity/assets/` is defined as one shared attachment directory
    for every language, so `assets` is only meaningful as the *first* segment
    below `entity_dir`; a Type or a slug that happens to be named `assets`
    is an ordinary page. This is the same rule `convert_wikilinks.py`'s
    `is_in_assets()` applies on the publish side.

    Matching is done on the path *below* `entity_dir`, never on `page.parts`.
    Callers pass `entity_dir` both relative and absolute (check_wikilinks.py
    builds `Path.cwd() / ENTITY_DIR`), and testing the full path also matches a
    repository that merely lives somewhere under a directory named `assets` —
    skipping every page, silently, with no error and only a smaller count to
    show for it (Issue #677).

    A path that cannot be resolved against `entity_dir` at all is reported as
    not-an-asset: it is outside the tree this rule describes, and the caller's
    own `parse_wiki_path()` is what decides whether such a file is a page.
    """
    try:
        rel_parts = page.resolve().relative_to(entity_dir.resolve()).parts
    except (ValueError, OSError, RuntimeError):
        return False
    return rel_parts[:1] == ("assets",)


def collect_entity_pages(
    entity_dir: Path = ENTITY_DIR, *, include_index: bool = False
) -> list[Path]:
    """Every wiki page under `entity_dir`, sorted, minus the two things that
    are never graph or aggregate material (Issue #677).

    Excluded: files under the top-level `assets/` (attachments, not pages) and
    `index.md` (generated per-Type navigation, which states no facts of its
    own). Pass `include_index=True` where the index pages themselves are the
    subject: `rebuild_index.py` needs them to find Type directories that no
    longer hold any page, `check_wikilinks.py`'s backlink walk counts a link
    from one as a real remaining reference, and `check_wanted_pages.py` keeps
    them because that is what it did before this walk was shared. Those three
    are the only callers that pass it.

    This condition had been written out independently in 18 places, and the
    `assets/` half of it had drifted into three different meanings. One copy
    was outright wrong (see `is_entity_asset()`), and it was wrong in the way
    that does not announce itself: the check it fed simply found nothing.
    Nothing here is new behaviour — it is the same walk those copies did,
    with the strictest and best-documented reading of each rule.

    Deliberately *not* the right helper for `validate_frontmatter.py` and
    `check_raw_html.py`: those verify every `.md` on disk, `assets/` and
    `index.md` included (the first has an explicit branch exempting `index.md`
    from requiring `sources`). Their subject is the files, not the page graph.
    """
    if not entity_dir.exists():
        return []
    pages = []
    for page in sorted(entity_dir.rglob("*.md")):
        if is_entity_asset(page, entity_dir):
            continue
        if not include_index and page.name == "index.md":
            continue
        pages.append(page)
    return pages


def parse_view_path(path: Path, view_dir: Path = VIEW_DIR) -> tuple[str, str, str] | None:
    """Derive (lang, "View", slug) from a view page path under view_dir.

    The middle element is the constant `VIEW_TYPE_SEGMENT` rather than anything
    read off the path, so the result has the same shape parse_wiki_path()
    returns for an entity page and callers holding both trees need no second
    code path. That constant is exactly what a `[[View/<slug>]]` link names.

    Returns None for anything that is not `<lang>/<slug>.md` — one segment then
    the file, no deeper. A view page has no Type directory, so a nested path is
    not a view page whose type could not be read; it is not a view page.
    """
    try:
        rel = path.resolve().relative_to(view_dir.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    parts = rel.parts
    if len(parts) != 2 or not parts[1].endswith(".md"):
        return None
    return parts[0], VIEW_TYPE_SEGMENT, parts[1].removesuffix(".md")


def collect_view_pages(view_dir: Path = VIEW_DIR, *, include_index: bool = False) -> list[Path]:
    """Every view page under `view_dir`, sorted, excluding the per-language
    `index.md` unless asked for (the same contract collect_entity_pages() has).

    There is no `assets/` exclusion to make: attachments live in the entity
    tree's single shared `assets/` directory, and a view page reaches them the
    same way any page does.
    """
    if not view_dir.exists():
        return []
    pages = []
    for page in sorted(view_dir.rglob("*.md")):
        if not include_index and page.name == "index.md":
            continue
        pages.append(page)
    return pages


def view_page_path(lang: str, slug: str, view_dir: Path = VIEW_DIR) -> Path:
    """Where the view page for `[[View/<slug>]]` in `lang` lives on disk."""
    return view_dir / lang / f"{slug}.md"


# A WikiLink resolves only when BOTH its Type segment and its slug match. A
# link that names the right slug under the wrong Type therefore reads as
# "target does not exist" to every gate, even though the page is right there
# under another Type — check_wikilinks.py reports the same WARNING it uses for
# a genuinely not-yet-written concept, and check_wanted_pages.py lists it as a
# page that ought to be created, which is the opposite of the correct fix
# (Issue #563). Both scripts need the same "is this slug used by some other
# Type?" lookup to tell the two apart, so it lives here rather than being
# implemented twice (this module's whole reason for existing — see the module
# docstring).
def build_slug_type_index(
    entity_dir: Path = ENTITY_DIR, view_dir: Path | None = VIEW_DIR
) -> dict[str, set[str]]:
    """Map each slug to the set of Types that have a linkable page for it,
    across every language.

    Language-agnostic on purpose: check_orphans.py already matches
    `[[Type/slug]]` against pages by slug regardless of language, and a Type
    segment is wrong (or right) independently of which language directory the
    page happens to live in.

    Two kinds of page are left out, because neither makes "you named the wrong
    Type" a true statement about an otherwise-fine link:

    - `index.md`, the per-Type index page `rebuild_index.py` generates. Its
      slug is an artifact of that mechanism, shared by every Type, so a match
      on it carries no information about the link's intent.
    - `status: removed` pages. Retargeting a link onto one only trades this
      report for check_wikilinks.py's removed-page ERROR; the honest reading
      is that no usable page backs the slug, which is what the unchanged
      WARNING / `WANTED:` path already says.

    View pages are indexed too, under the reserved `View` Type (Issue #675).
    A wiki that moves a synthesized page out of `custom/Practice/` and into the
    view tree leaves every `[[custom/Practice/<slug>]]` link behind it pointing
    at nothing; without this the link reads as "nobody has written that page",
    when the page is right there and the fix is the one-word Type segment.
    """
    pairs: list[tuple[Path, Path, bool]] = [(page, entity_dir, False) for page in collect_entity_pages(entity_dir)]
    if view_dir is not None:
        pairs += [(page, view_dir, True) for page in collect_view_pages(view_dir)]

    index: dict[str, set[str]] = {}
    for page, tree_dir, is_view in pairs:
        resolved = parse_view_path(page, tree_dir) if is_view else parse_wiki_path(page, tree_dir)
        if resolved is None:
            continue
        _, type_name, slug = resolved
        # err is "" on success, never None (see _frontmatter.py). A page whose
        # frontmatter does not parse is kept as a candidate: the honest reading
        # is "a file backs this slug", and the malformed frontmatter itself is
        # validate_frontmatter.py's finding to report, not this one's.
        fm, err = parse_frontmatter_cached(page)
        if not err and isinstance(fm, dict) and fm.get("status") == "removed":
            continue
        index.setdefault(slug, set()).add(type_name)
    return index


def other_types_for_slug(
    type_name: str, slug: str, slug_index: dict[str, set[str]]
) -> list[str]:
    """Types other than `type_name` that have a page for `slug`, sorted.

    Empty when the slug is unused elsewhere — i.e. the link really does point
    at a page nobody has written yet, and Issue #340's non-blocking treatment
    still applies. All matching Types are returned rather than one best guess:
    the script cannot know which one the author meant, and naming them all is
    what lets a human pick in one step.
    """
    return sorted(t for t in slug_index.get(slug, set()) if t != type_name)
