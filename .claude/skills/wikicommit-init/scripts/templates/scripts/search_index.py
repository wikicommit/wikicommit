#!/usr/bin/env python3
"""Build and query the shared FTS5 trigram search index for the wiki.

Used by both the wikicommit-search and wikicommit-ask Skills
(docs/DesignDoc-skills.md §11.5: scripts called by multiple Skills live in
.wikicommit/scripts/).

Usage:
    python .wikicommit/scripts/search_index.py build
    python .wikicommit/scripts/search_index.py query "<query>" [--lang <lang>] [--limit N]

Exit code: 0 = success (0 hits is still success), 1 = SQLite lacks the FTS5
trigram tokenizer, or .wikicommit/entity/ does not exist.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text
from _wikilink import ENTITY_DIR
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
    if not ENTITY_DIR.exists():
        return []
    return sorted(
        p for p in ENTITY_DIR.rglob("*.md")
        if "assets" not in p.parts and p.name != "index.md"
    )


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
    if not ENTITY_DIR.exists():
        print(f"ERROR: {ENTITY_DIR} が存在しません")
        return 1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    try:
        if not _create_index_table(con):
            con.close()
            DB_PATH.unlink(missing_ok=True)
            print(
                "ERROR: SQLite の FTS5 trigram トークナイザが利用できません "
                f"(sqlite3.sqlite_version={sqlite3.sqlite_version}, SQLite 3.34+ が必要・3.38+ 推奨)"
            )
            return 1

        rows = []
        for page in collect_pages():
            fm, body = _parse_page(page)
            if fm is None or fm.get("status") == "removed":
                continue
            rows.append((
                str(page),
                str(fm.get("title") or ""),
                str(fm.get("lang") or ""),
                str(fm.get("type") or ""),
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


def _fts5_query(terms: list[str]) -> str:
    """Build an FTS5 MATCH expression from a list of query terms.

    Each term is quoted as its own phrase so stray MATCH-syntax characters
    (e.g. '-', '"', '*') in user input can't raise a query syntax error,
    while adjacent terms stay implicitly AND-ed — a multi-word query still
    matches a page where the terms co-occur but aren't literally adjacent
    (quoting the whole query as one phrase would require an exact substring
    match instead)."""
    if not terms:
        return '""'
    return " ".join('"' + t.replace('"', '""') + '"' for t in terms)


# The trigram tokenizer can only form tokens from runs of 3+ characters, so a
# query term shorter than this can never match anything (Issue #274) — it
# silently drops that term's contribution to the AND-ed match instead of
# raising an error. Surfacing this lets callers (wikicommit-search /
# wikicommit-ask) explain an unexpected hits=0 instead of it looking like a
# search bug when matching content actually exists.
MIN_TRIGRAM_TERM_LENGTH = 3


def _short_terms(terms: list[str]) -> list[str]:
    return [t for t in terms if len(t) < MIN_TRIGRAM_TERM_LENGTH]


def query_index(query: str, lang: str | None, limit: int) -> int:
    if not DB_PATH.exists():
        result = build_index()
        if result != 0:
            return result

    terms = query.split()
    for term in _short_terms(terms):
        print(
            f'WARNING: query term "{term}" has {len(term)} character(s); '
            f"trigram search requires at least {MIN_TRIGRAM_TERM_LENGTH} and this term cannot match anything"
        )

    con = sqlite3.connect(DB_PATH)
    try:
        sql = (
            "SELECT path, title, type, lang, review_status, "
            "snippet(pages, 6, '**', '**', '...', ?) AS snip "
            "FROM pages WHERE pages MATCH ?"
        )
        params: list = [SNIPPET_MAX_TOKENS, _fts5_query(terms)]
        if lang:
            sql += " AND lang = ?"
            params.append(lang)
        sql += " ORDER BY bm25(pages, ?, ?, ?, ?, ?, ?, ?) LIMIT ?"
        params.extend(BM25_WEIGHTS)
        params.append(limit)

        try:
            rows = con.execute(sql, params).fetchall()
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            print(f"ERROR: 検索クエリの実行に失敗しました: {e}")
            return 1

        for path, title, type_, page_lang, review_status, snip in rows:
            print(f"MATCH: {path} | title={title} | type={type_} | lang={page_lang} | review_status={review_status}")
            print(f"  {snip}")

        print(f'SUMMARY: query="{query}", hits={len(rows)}')
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and query the wiki FTS5 trigram search index.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("build", help="Rebuild the search index from .wikicommit/entity/.")

    query_parser = subparsers.add_parser("query", help="Search the index.")
    query_parser.add_argument("query", help="Search query text.")
    query_parser.add_argument("--lang", default=None, help="Filter results to this language.")
    query_parser.add_argument("--limit", type=int, default=10, help="Maximum number of results (default 10).")

    args = parser.parse_args()

    if args.command == "build":
        return build_index()
    return query_index(args.query, args.lang, args.limit)


if __name__ == "__main__":
    sys.exit(main())
