#!/usr/bin/env python3
"""check_extraction_quality.py — shared by wikicommit-generate and wikicommit-collect.

Pass 1's original extraction-failure check only catches text that is empty or
unreadable. It does not catch text that is non-empty but useless: a
JavaScript-rendering-required page fetched with a static tool (markitdown,
curl) can return a non-empty "shell" (nav links, login prompts, embedded
JSON/JS state) with none of the page's actual content. This was confirmed for
https://x.com/karpathy/status/1886192184808149383 in the ai-driven-dev-wiki
pilot: the management file recorded status: generated with 1060
extracted_tokens, but the extracted text contained zero occurrences of the
tweet's own wording — see Issue #425 for the full writeup.

This script implements the two checks Issue #425 designed for that gap:

(B) check-domain: run *before* attempting extraction, from the URL alone.
    Domains confirmed to sometimes return an empty shell are skipped outright
    (no fetch attempted) — precise but only covers domains someone has
    already observed failing this way.
(A) check-density: run *after* extraction, on the extracted text. A general,
    domain-agnostic heuristic that estimates what fraction of the text looks
    like natural-language prose versus markup/code/data. Lower precision than
    (B), but catches domains nobody has flagged yet.

See docs/DesignDoc-pipeline.md §6.1 and docs/DesignDoc-skills.md §11.6 for how
wikicommit-generate's Pass 1 and wikicommit-collect's candidate search use
these two checks.

Usage:
    python .wikicommit/scripts/check_extraction_quality.py check-domain <url>
    python .wikicommit/scripts/check_extraction_quality.py check-density <file>

Exit code: 0 = OK, 1 = blocked (check-domain) / low density (check-density) /
file could not be read (check-density).
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

# Domains confirmed to sometimes return an empty content shell via static
# fetch (markitdown/curl) because real content only appears after JS
# execution. Extend this set only after confirming the empty-shell behavior
# directly (as Issue #425 did for x.com/twitter.com) — an unconfirmed entry
# would silently skip extraction for a domain that might actually work fine.
KNOWN_JS_SHELL_DOMAINS = {
    "x.com",
    "twitter.com",
}

# Below this natural-language character ratio (see _natural_char_ratio),
# extracted text is treated as low-density boilerplate/markup rather than
# real content. Validated against the fixtures in
# tests/test_check_extraction_quality.py; adjust both together if this proves
# too strict/loose against real-world extraction results.
LOW_DENSITY_THRESHOLD = 0.3

# Characters whose mere presence in a token marks it as markup/code rather
# than prose, regardless of how alphabetic the rest of the token is (a JSON
# key or JS identifier is mostly letters too, so alpha-ratio alone can't
# distinguish `{"loaderData":null}` from a real word).
_STRUCTURAL_CHARS = set("{}<>;=")


def _domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[len("www."):]
    return host


def check_domain(url: str) -> int:
    domain = _domain_of(url)
    if domain in KNOWN_JS_SHELL_DOMAINS:
        print(
            f"BLOCKED: {domain} is a known JS-rendering-required domain; "
            f"static fetch (markitdown/curl) has been confirmed to sometimes "
            f"return an empty content shell with no meaningful text. "
            f"See docs/DesignDoc-pipeline.md §6.1 (Issue #425)."
        )
        return 1
    print(f"OK: {domain} is not a known JS-shell domain")
    return 0


def _is_natural_token(token: str) -> bool:
    if any(c in _STRUCTURAL_CHARS for c in token):
        return False
    if token.count('"') > 1 or "`" in token:
        return False
    if "://" in token:
        # A URL (bare, or as the target half of a Markdown link) is markup,
        # not prose — its alpha-dominant characters (scheme, host, path
        # segments) would otherwise pass the ratio check below and make
        # link-heavy boilerplate look artificially prose-like.
        return False
    core = token.strip("[]()*_.,:!?~|\\/'\"")
    if len(core) < 2:
        return False
    alpha_count = sum(1 for c in core if c.isalpha())
    return alpha_count / len(core) >= 0.7


def _natural_char_ratio(text: str) -> float:
    """Fraction of whitespace-token characters that look like natural-language
    words, weighted by character count rather than token count so CJK text
    (which has no inter-word spaces and so forms few, long tokens) isn't
    penalized relative to space-delimited languages."""
    tokens = text.split()
    total_chars = sum(len(t) for t in tokens)
    if total_chars == 0:
        return 0.0
    natural_chars = sum(len(t) for t in tokens if _is_natural_token(t))
    return natural_chars / total_chars


def check_density(path: str | None) -> int:
    label = path if path else "<stdin>"
    try:
        if path:
            text = Path(path).read_text(encoding="utf-8-sig")
        else:
            text = sys.stdin.read()
    except OSError as e:
        print(f"ERROR: {label}: could not read file: {e}", file=sys.stderr)
        return 1

    ratio = _natural_char_ratio(text)
    if ratio < LOW_DENSITY_THRESHOLD:
        print(
            f"LOW_DENSITY: {label} (natural-language character ratio: "
            f"{ratio:.2f}, threshold: {LOW_DENSITY_THRESHOLD}) — extracted "
            f"text looks like boilerplate/markup rather than real content."
        )
        return 1
    print(f"OK: {label} (natural-language character ratio: {ratio:.2f})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_domain = sub.add_parser(
        "check-domain", help="Check whether a URL's domain is a known JS-shell domain"
    )
    p_domain.add_argument("url")

    p_density = sub.add_parser(
        "check-density",
        help="Check whether extracted text has low information density (reads stdin if <file> is omitted)",
    )
    p_density.add_argument("file", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "check-domain":
        return check_domain(args.url)
    return check_density(args.file)


if __name__ == "__main__":
    sys.exit(main())
