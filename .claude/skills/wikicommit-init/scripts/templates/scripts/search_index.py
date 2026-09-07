#!/usr/bin/env python3
"""Build and query the shared FTS5 trigram search index for the wiki.

Used by both the wikicommit-search and wikicommit-ask Skills (scripts called
by more than one Skill live in .wikicommit/scripts/).

Usage:
    python .wikicommit/scripts/search_index.py build
    python .wikicommit/scripts/search_index.py query "<query>" [--lang <lang>] [--limit N]
    python .wikicommit/scripts/search_index.py query --expand "<a>|<b>" --expand "<c>" [--lang <lang>] [--limit N]

Exit code: 0 = success (0 hits is still success), 1 = SQLite lacks the FTS5
trigram tokenizer, .wikicommit/entity/ does not exist, or the query arguments
are contradictory (both a positional query and --expand, or neither).
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text
from _wikilink import (
    ENTITY_DIR,
    VIEW_DIR,
    VIEW_TYPE_SEGMENT,
    collect_entity_pages,
    collect_view_pages,
)
CACHE_DIR = Path(".wikicommit/.cache")
DB_PATH = CACHE_DIR / "search_index.sqlite3"

# bm25() takes one weight per column in table-definition order (path, title,
# lang, type, tags, review_status, body), including UNINDEXED columns. Title
# hits are weighted far above body hits per the Issue #126 spec; UNINDEXED
# columns take a placeholder 0.0 since they are never part of the MATCH.
BM25_WEIGHTS = (0.0, 10.0, 0.0, 0.0, 0.0, 0.0, 1.0)

# snippet()'s max_tokens counts trigram tokens (3-char, overlapping by 2), so
# N tokens span roughly N+2 characters. 64 gives a "~32 chars either side of
# the match" snippet as called for by the Issue #126 spec.
SNIPPET_MAX_TOKENS = 64


def collect_pages() -> list[Path]:
    # View pages are indexed alongside entity pages (Issue #675). They are
    # readable wiki content and the whole point of writing one is that a
    # reader can find it; the exclusion Issue #674 introduced applies only to
    # the grounding set a synthesis is built from, not to search.
    return collect_entity_pages(ENTITY_DIR) + collect_view_pages(VIEW_DIR)


def _parse_page(path: Path) -> tuple[dict | None, str]:
    """Return (frontmatter dict, body text with frontmatter stripped).

    Returns (None, body) when the frontmatter can't be read as a mapping, so
    the caller can skip the page instead of risking indexing (and thereby
    exposing via search) a page whose real `status: removed` can't be seen.
    """
    content = path.read_text(encoding="utf-8-sig")
    fm, err, body = parse_frontmatter_and_body_text(content)
    if err:
        print(f"WARNING: {path}: {err}")
        return None, body
    return fm, body


def _tags_to_text(tags_raw: object) -> str:
    if isinstance(tags_raw, list):
        return " ".join(str(t) for t in tags_raw)
    if tags_raw is None:
        return ""
    return str(tags_raw)


def _create_index_table(con: sqlite3.Connection) -> bool:
    """Create the FTS5 trigram virtual table. Return False if unsupported."""
    try:
        con.execute("DROP TABLE IF EXISTS pages")
        con.execute(
            "CREATE VIRTUAL TABLE pages USING fts5("
            "path UNINDEXED, title, lang UNINDEXED, type UNINDEXED, "
            'tags, review_status UNINDEXED, body, tokenize="trigram")'
        )
    except sqlite3.OperationalError:
        return False
    return True


def build_index() -> int:
    if not ENTITY_DIR.exists() and not VIEW_DIR.exists():
        print(f"ERROR: {ENTITY_DIR} does not exist")
        return 1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    try:
        if not _create_index_table(con):
            con.close()
            DB_PATH.unlink(missing_ok=True)
            print(
                "ERROR: the SQLite FTS5 trigram tokenizer is unavailable "
                f"(sqlite3.sqlite_version={sqlite3.sqlite_version}; SQLite 3.34+ required, 3.38+ recommended)"
            )
            return 1

        # Which tree a page came from is already known here — collect_pages()
        # walked the two separately — so it is recorded once rather than
        # re-derived per page with parse_view_path(), which resolve()s both the
        # page and VIEW_DIR on every entity page only to answer None.
        view_pages = set(collect_view_pages(VIEW_DIR))

        rows = []
        for page in collect_pages():
            fm, body = _parse_page(page)
            if fm is None or fm.get("status") == "removed":
                continue
            rows.append((
                str(page),
                str(fm.get("title") or ""),
                str(fm.get("lang") or ""),
                # A view page has no `type:` (Issue #675); show the reserved
                # `View` segment instead, which is both what a reader would
                # write in a WikiLink to it and non-empty in the result line.
                (VIEW_TYPE_SEGMENT if page in view_pages else str(fm.get("type") or "")),
                _tags_to_text(fm.get("tags")),
                str(fm.get("review_status") or "pending"),
                body,
            ))

        con.executemany(
            "INSERT INTO pages (path, title, lang, type, tags, review_status, body) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()
        print(f"OK: indexed {len(rows)} pages -> {DB_PATH}")
        return 0
    finally:
        con.close()


def _fts5_phrase(term: str) -> str:
    """Quote one term as an FTS5 phrase.

    Quoting is what keeps stray MATCH-syntax characters (e.g. '-', '"', '*')
    in user input from raising a query syntax error; an embedded double quote
    is escaped by doubling it, as FTS5 requires."""
    return '"' + term.replace('"', '""') + '"'


def _fts5_query(terms: list[str]) -> str:
    """Build an FTS5 MATCH expression from a list of query terms.

    Each term is quoted as its own phrase, while adjacent terms stay
    implicitly AND-ed — a multi-word query still matches a page where the
    terms co-occur but aren't literally adjacent (quoting the whole query as
    one phrase would require an exact substring match instead)."""
    if not terms:
        return '""'
    return " ".join(_fts5_phrase(t) for t in terms)


def _fts5_group_query(groups: list[list[str]]) -> str:
    """Build an FTS5 MATCH expression from groups of synonymous terms.

    Terms inside a group are OR-ed; the groups are AND-ed. That is the shape a
    query expansion needs (Issue #581): the expanded terms are alternative
    wordings of one concept, so adding them must widen the match, whereas
    appending them to the flat implicitly-AND-ed list `_fts5_query` builds
    would narrow it to pages containing every wording at once.

    Every group is parenthesised and the groups are joined with an explicit
    `AND`, including single-term groups. FTS5 rejects a parenthesised
    expression sitting next to a bare phrase (`("a" OR "b") "c"` is a syntax
    error) and rejects two juxtaposed parenthesised groups as well, so the
    explicit operator is required as soon as any group exists — there is no
    mixed form to fall back to."""
    parts = ["(" + " OR ".join(_fts5_phrase(t) for t in g) + ")" for g in groups if g]
    if not parts:
        return '""'
    return " AND ".join(parts)


def parse_expand_groups(values: list[str]) -> list[list[str]]:
    """Split each --expand value on '|' into a group of synonymous terms.

    Blank terms (from a stray leading/trailing/doubled separator) are dropped,
    as is a group left empty by that. A term containing '|' itself cannot be
    expressed; that is accepted deliberately rather than adding an escape
    syntax for a separator no realistic search term contains.

    Each surviving term has every run of whitespace collapsed to one space.
    A multi-word term is meant to be one adjacency phrase, so the whitespace
    is not a separator here — but a *newline* left inside a term would reach
    the `SUMMARY: query=..., hits=N` line, and every Skill that calls this
    script parses that line by line. One heredoc holding two groups on two
    lines (an easy slip given the documented `--expand "$(cat <<'EOF' ...`
    form) would then split the summary across lines and hide `hits=` from the
    caller. The positional path never had this problem because `query.split()`
    treats newlines as separators."""
    groups = []
    for value in values:
        terms = [" ".join(t.split()) for t in value.split("|")]
        terms = [t for t in terms if t]
        if terms:
            groups.append(terms)
    return groups


# The trigram tokenizer can only form tokens from runs of 3+ characters, so a
# query term shorter than this can never match anything (Issue #274) — it
# silently drops that term's contribution to the AND-ed match instead of
# raising an error. Surfacing this lets callers (wikicommit-search /
# wikicommit-ask) explain an unexpected hits=0 instead of it looking like a
# search bug when matching content actually exists.
MIN_TRIGRAM_TERM_LENGTH = 3


def _short_terms(terms: list[str]) -> list[str]:
    return [t for t in terms if len(t) < MIN_TRIGRAM_TERM_LENGTH]


def _prune_short_group_terms(groups: list[list[str]]) -> list[list[str]]:
    """Warn about sub-trigram terms in expansion groups and drop them.

    Two distinct outcomes, hence two distinct messages (Issue #581). A group
    that keeps at least one usable term still matches through that term, so a
    short term there is only noise being removed — expansion rescuing a short
    original via a longer synonym is a feature, and reporting it in the same
    alarming words as a dead query would be misleading. A group with no usable
    term left matches nothing at all, and because groups are AND-ed an operand
    that matches nothing would zero out the whole query. Dropping the group
    instead keeps this consistent with the positional path, where FTS5's
    implicit AND already discards a short phrase's contribution rather than
    failing the match; the cost is that the concept stops constraining the
    search, which the message says outright."""
    pruned = []
    for group in groups:
        usable = [t for t in group if len(t) >= MIN_TRIGRAM_TERM_LENGTH]
        for term in group:
            if len(term) >= MIN_TRIGRAM_TERM_LENGTH:
                continue
            if usable:
                print(
                    f'WARNING: expand term "{term}" has {len(term)} character(s); '
                    f"trigram search requires at least {MIN_TRIGRAM_TERM_LENGTH}, so it was dropped — "
                    f'its group still matches via: {", ".join(usable)}'
                )
            else:
                print(
                    f'WARNING: expand group "{"|".join(group)}" has no term of at least '
                    f"{MIN_TRIGRAM_TERM_LENGTH} character(s); trigram search cannot match any of them, "
                    "so this group was dropped and no longer narrows the search"
                )
                break
        if usable:
            pruned.append(usable)
    return pruned


def query_index(
    query: str | None, lang: str | None, limit: int, expand: list[str] | None = None
) -> int:
    if not DB_PATH.exists():
        result = build_index()
        if result != 0:
            return result

    if expand:
        groups = _prune_short_group_terms(parse_expand_groups(expand))
        if not groups:
            # Every group was blank or pruned away, so the expression below is
            # the empty phrase and the search can only ever return 0 hits. Say
            # so explicitly: without this the run is either silent (a blank
            # --expand value) or, worse, carries only the per-group message
            # above, which says the search stopped being narrowed — the
            # opposite of what happens when nothing is left to narrow.
            print(
                "WARNING: no usable --expand term remains; the search has no terms at all "
                "and cannot match anything (this is not a wiki-coverage result)"
            )
        match_expr = _fts5_group_query(groups)
        # The expanded expression, not the raw arguments, is what actually ran:
        # terms were regrouped and short ones dropped, and a caller showing the
        # user which words produced these hits (wikicommit-search) needs the
        # form that is true. It is printed unquoted because it contains its own
        # quotes; it always starts with '(' unless nothing survived.
        summary_query = match_expr
    else:
        terms = (query or "").split()
        for term in _short_terms(terms):
            print(
                f'WARNING: query term "{term}" has {len(term)} character(s); '
                f"trigram search requires at least {MIN_TRIGRAM_TERM_LENGTH} and this term cannot match anything"
            )
        match_expr = _fts5_query(terms)
        summary_query = f'"{query or ""}"'

    con = sqlite3.connect(DB_PATH)
    try:
        sql = (
            "SELECT path, title, type, lang, review_status, "
            "snippet(pages, 6, '**', '**', '...', ?) AS snip "
            "FROM pages WHERE pages MATCH ?"
        )
        params: list = [SNIPPET_MAX_TOKENS, match_expr]
        if lang:
            sql += " AND lang = ?"
            params.append(lang)
        sql += " ORDER BY bm25(pages, ?, ?, ?, ?, ?, ?, ?) LIMIT ?"
        params.extend(BM25_WEIGHTS)
        params.append(limit)

        try:
            rows = con.execute(sql, params).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            print(f"ERROR: the search query failed: {e}")
            return 1

        for path, title, type_, page_lang, review_status, snip in rows:
            print(f"MATCH: {path} | title={title} | type={type_} | lang={page_lang} | review_status={review_status}")
            print(f"  {snip}")

        print(f"SUMMARY: query={summary_query}, hits={len(rows)}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and query the wiki FTS5 trigram search index.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Rebuild the search index from .wikicommit/entity/.")

    query_parser = subparsers.add_parser("query", help="Search the index.")
    query_parser.add_argument(
        "query", nargs="?", default=None, help="Search query text (terms are AND-ed)."
    )
    query_parser.add_argument(
        "--expand",
        action="append",
        default=None,
        metavar="TERM|TERM",
        help=(
            "One concept's terms, '|'-separated (synonyms, abbreviations, cross-language "
            "equivalents). Repeat for each concept: terms within a group are OR-ed, groups "
            "are AND-ed. Mutually exclusive with the positional query."
        ),
    )
    query_parser.add_argument("--lang", default=None, help="Filter results to this language.")
    query_parser.add_argument("--limit", type=int, default=10, help="Maximum number of results (default 10).")

    args = parser.parse_args()

    if args.command == "build":
        return build_index()

    # Rejected rather than merged: the two forms carry different semantics for
    # the same words (flat AND vs. grouped OR/AND), so silently combining them
    # would search for something the caller did not ask for.
    if args.query is not None and args.expand:
        print("ERROR: the positional query and --expand cannot both be given; use one or the other")
        return 1
    if args.query is None and not args.expand:
        print("ERROR: no search term; give either the positional query or --expand")
        return 1

    return query_index(args.query, args.lang, args.limit, expand=args.expand)


if __name__ == "__main__":
    sys.exit(main())
