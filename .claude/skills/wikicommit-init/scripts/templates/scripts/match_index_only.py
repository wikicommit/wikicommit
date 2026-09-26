#!/usr/bin/env python3
"""Match URLs against `index_only:` in .wikicommit/source-policy.md (Issue #1032).

`index_only:` names what this wiki reads for the sources it cites and never
registers (Issue #570). An entry takes one of two shapes, and the shape is the
meaning:

    - en.wikipedia.org                          # a domain: that whole host
    - https://github.com/example/awesome-foo    # a page: that one page

What separates them is whether the entry pins down a single URL to fetch. A page
does, so /wikicommit-collect can go and mine it on its own initiative; a domain
does not, so it can only be matched when a search result happens to land on it.

Until Issue #1032 the matching was done in prose, in two SKILL.md files
(wikicommit-collect step 5 and wikicommit-generate step 0), and the rule threw the
path away, so every entry meant a whole host. With two shapes to tell apart, two
copies of the rule in prose would drift apart independently — this is the shape
Issue #474 named (a deterministic operation expressed as an instruction), so the
rule lives here once and both Skills call it.

Normalization:

- Domain entry: scheme, port, any path and a leading `www.` are dropped and the
  host is lowercased. Matching is on the exact host — `example.com` does not
  cover `blog.example.com` — the same rule check_extraction_quality.py applies to
  `exclude_domains`.
- Page entry: scheme, a leading `www.`, the fragment and a trailing slash are
  dropped, the host is lowercased and the path is percent-decoded (an article URL
  is as likely to be pasted with `%E3%81%95` as with the character itself). The
  query is **kept** (percent-decoded like the path) and compared exactly: on sites where the query is what names
  the page (`index.php?title=X`, `watch?v=…`), dropping it would turn one page into
  every page on that path.

An entry is a page when, after normalization, anything remains beyond the host
(a path other than `/`, or a query). Before Issue #1032 such an entry meant the
whole host; it now means that one page. No public pilot had one (checked
2026-09-25), and CHANGELOG.md says so for anyone who did.

Reads only. A policy file that exists but cannot be parsed is reported on stderr
and treated as having no entries, the same way check_extraction_quality.py
handles `exclude_domains` — a malformed append to `rejected:` must not switch the
list off with nothing to say about it, and it must not break the caller either.

Usage:

    python .wikicommit/scripts/match_index_only.py match <url>
    python .wikicommit/scripts/match_index_only.py list-pages

`match` prints `INDEX_ONLY: <url> (matches <entry>, <domain|page>)` or
`OK: <url> is not listed under index_only`. `list-pages` prints one
`PAGE: <url>` line per page entry, as written in the file, then a `SUMMARY:` line.
Both always exit 0; the prefix is the answer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

from _frontmatter import parse_frontmatter

SOURCE_POLICY_PATH = Path(".wikicommit/source-policy.md")


def _split(raw: str):
    value = raw.strip()
    # urlsplit only fills netloc when it sees an authority; "//" makes a bare
    # host (or a "host/path" entry) parse as one, and a real scheme still works.
    if "://" not in value:
        value = "//" + value.lstrip("/")
    return urlsplit(value)


def _host(parts) -> str:
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[len("www."):]
    return host


def normalize(raw: str) -> tuple[str, str | None] | None:
    """Return (host, page) for an entry or a URL; page is None for a bare domain.

    None when nothing usable is left (an empty entry, or one with no host).
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parts = _split(raw)
        host = _host(parts)
    except ValueError:
        # urlsplit rejects e.g. an unbalanced "[" as an invalid IPv6 host. One bad
        # entry (or a bad candidate URL) must not crash every lookup: the contract
        # is exit 0 with the prefix as the answer.
        return None
    if not host:
        return None
    path = unquote(parts.path).rstrip("/")
    # Decoded for the same reason as the path: `?title=%E3%81%95` and
    # `?title=さ` name the same page.
    query = unquote(parts.query)
    if not path and not query:
        return host, None
    return host, path + (f"?{query}" if query else "")


def policy_entries(path: Path = SOURCE_POLICY_PATH) -> list[tuple[str, tuple[str, str | None]]]:
    """(entry as written, normalized form) for every usable `index_only:` entry."""
    if not path.exists():
        return []
    frontmatter, error = parse_frontmatter(path)
    if error:
        print(
            f"WARNING: {path}: {error} — wikicommit.index_only is being ignored "
            f"for this check.",
            file=sys.stderr,
        )
        return []
    if not isinstance(frontmatter, dict):
        return []
    block = frontmatter.get("wikicommit")
    if not isinstance(block, dict):
        return []
    raw_entries = block.get("index_only")
    if not isinstance(raw_entries, list):
        return []
    entries = []
    for raw in raw_entries:
        norm = normalize(raw) if isinstance(raw, str) else None
        if norm:
            entries.append((raw.strip(), norm))
    return entries


def find_match(url: str, entries) -> tuple[str, str] | None:
    """(entry as written, "domain" | "page") for the first entry url matches."""
    target = normalize(url)
    if target is None:
        return None
    host, page = target
    for raw, (e_host, e_page) in entries:
        if e_host != host:
            continue
        if e_page is None:
            return raw, "domain"
        if e_page == page:
            return raw, "page"
    return None


def cmd_match(url: str, path: Path) -> int:
    match = find_match(url, policy_entries(path))
    if match:
        raw, kind = match
        print(f"INDEX_ONLY: {url} (matches {raw}, {kind})")
    else:
        print(f"OK: {url} is not listed under index_only")
    return 0


def cmd_list_pages(path: Path) -> int:
    pages = [raw for raw, (_host, page) in policy_entries(path) if page is not None]
    for raw in pages:
        print(f"PAGE: {raw}")
    print(f"SUMMARY: index_only_pages={len(pages)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--policy", default=str(SOURCE_POLICY_PATH), help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="command", required=True)
    p_match = sub.add_parser("match", help="Report whether a URL is listed under index_only")
    p_match.add_argument("url")
    sub.add_parser("list-pages", help="List the page (not domain) entries under index_only")
    args = parser.parse_args(argv)
    path = Path(args.policy)
    if args.command == "match":
        return cmd_match(args.url, path)
    return cmd_list_pages(path)


if __name__ == "__main__":
    sys.exit(main())
