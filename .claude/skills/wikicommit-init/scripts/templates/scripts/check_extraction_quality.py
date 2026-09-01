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
(C) check-fetch-capability: run *before* attempting extraction, from the URL
    alone. Some hosts need an optional Python package for markitdown to reach
    the part of the page that actually carries the content — for YouTube, the
    video's transcript comes only from `youtube_transcript_api`, and without it
    markitdown silently returns just the title/keywords/runtime/description
    with no error at all (Issue #574). That is a different axis from (A) and
    (B): the page is neither an empty shell nor low-density prose, it is a
    genuine partial extraction, so neither of the other two guards can see it.
(A) check-density: run *after* extraction, on the extracted text. A general,
    domain-agnostic heuristic that estimates what fraction of the text looks
    like natural-language prose versus markup/code/data. Lower precision than
    (B), but catches domains nobody has flagged yet.

The two guards are deliberately *not* equally strong (Issue #562). (B) is a
deterministic verdict about a domain someone has already confirmed broken, so
wikicommit-generate treats its exit 1 as blocking. (A) is a shape heuristic,
and a link-dense government site or a statistics table has essentially the same
text shape as a JS shell — the saitama-wiki pilot saw 4 of 8 genuine sources
flagged, and the operator overrode every one. Its exit 1 is therefore a warning
that Pass 1 raises with the human, not an automatic failure; the LOW_DENSITY
line carries a breakdown of the non-prose characters so that decision has
something concrete behind it.

wikicommit-generate's Pass 1 runs all three checks; wikicommit-collect's
candidate search runs check-domain only.

Usage:
    python .wikicommit/scripts/check_extraction_quality.py check-domain <url>
    python .wikicommit/scripts/check_extraction_quality.py check-fetch-capability <url>
    python .wikicommit/scripts/check_extraction_quality.py check-density <file>

Exit code: 0 = OK, 1 = blocked (check-domain, blocking) / missing package
(check-fetch-capability, blocking) / low density
(check-density, warning — see above) / file could not be read (check-density).
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from _frontmatter import parse_frontmatter

# Domains confirmed to sometimes return an empty content shell via static
# fetch (markitdown/curl) because real content only appears after JS
# execution. Extend this set only after confirming the empty-shell behavior
# directly (as Issue #425 did for x.com/twitter.com) — an unconfirmed entry
# would silently skip extraction for a domain that might actually work fine.
KNOWN_JS_SHELL_DOMAINS = {
    "x.com",
    "twitter.com",
    # YouTube Music is a client-rendered app and, unlike the other YouTube
    # hosts, does not redirect to www.youtube.com/watch — so markitdown's
    # YouTubeConverter never accepts it (its accepts() requires the literal
    # "https://www.youtube.com/watch?" prefix on the post-redirect URL) and the
    # HTML converter runs instead. Confirmed directly (Issue #574): fetching
    # https://music.youtube.com/watch?v=... yields ~185 characters of
    # "YouTube Music is not optimized for your browser" boilerplate with none
    # of the video's title, description or transcript — and that boilerplate is
    # ordinary prose, so guard A scores it 0.66 and lets it through.
    "music.youtube.com",
}

# Below this natural-language character ratio (see _density_report),
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

# Characters that make up numeric/tabular content (digits, thousands
# separators, units, and the pipes markitdown emits for table cells). Used
# only to label *why* a token was counted as non-prose in the breakdown the
# LOW_DENSITY line reports — never to decide whether it is prose.
_NUMERIC_CHARS = set("0123456789,.%-+/|:")

# Weight applied to a CJK character when measuring text (Issue #562). The
# ratio below is character-weighted, and a CJK character carries far more
# content than a Latin one — WikiCommit's own extracted_tokens heuristic
# assumes ~4 Latin characters per token while a CJK character is roughly one
# token on its own. Counting both as "1 character" therefore under-measures
# CJK prose against the same markup, so equivalent Japanese and English prose
# with the same link density scored far apart. 3 is the conservative end of
# that 3-4x range. Note this weight can only ever move a text containing CJK:
# it is a no-op on the ASCII JS/nav-shell fixtures guard A exists to catch.
CJK_CHAR_WEIGHT = 3

# Unicode ranges treated as CJK for CJK_CHAR_WEIGHT: CJK symbols/punctuation,
# hiragana, katakana, CJK ideographs (incl. extension A), Hangul syllables,
# CJK compatibility ideographs, and halfwidth katakana.
_CJK_RANGES = (
    (0x3000, 0x30FF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xAC00, 0xD7AF),
    (0xF900, 0xFAFF),
    (0xFF66, 0xFF9F),
)


def _weight(text: str) -> int:
    return sum(
        CJK_CHAR_WEIGHT if any(lo <= ord(c) <= hi for lo, hi in _CJK_RANGES) else 1
        for c in text
    )


# Ranges a URL is never allowed to run into: the CJK ranges above plus the
# fullwidth ASCII/punctuation forms (`（`, `）`, `！`…). A URI is ASCII-only, so
# stopping there costs nothing for real link targets, and it is what keeps a
# *bare* URL from swallowing the prose that follows it. Without this, the
# terminator set below (whitespace and Markdown link/quote delimiters only)
# never fires in a language with no inter-word spaces: `参照 https://example.com/a、
# 以下この資料による。` matched as one giant "URL", and since a URL never counts
# as prose it took the prose with it — the same fusion _tokenize() exists to
# undo, one layer further in (Issue #562).
_URL_STOP_RANGES = _CJK_RANGES + ((0xFF01, 0xFF65),)

_URL_STOP_CLASS = "".join(f"\\u{lo:04X}-\\u{hi:04X}" for lo, hi in _URL_STOP_RANGES)

# Matches a URL as it appears in extracted Markdown: with a scheme
# (`https://…`), protocol-relative (`//upload.wikimedia.org/…`, which is what
# markitdown emits for Wikipedia image thumbnails), or bare (`www.example.com`).
# Terminates on whitespace, a Markdown link/quote delimiter, or any character in
# _URL_STOP_RANGES, so that `](https://example.com)` yields just the URL.
_URL_RE = re.compile(
    r"(?:[a-z][a-z0-9+.\-]*://|//(?=[A-Za-z0-9-]+\.[A-Za-z]{2,})|www\.)"
    r"[^\s)\]\"'<>" + _URL_STOP_CLASS + r"]+",
    re.I,
)


def _domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[len("www."):]
    return host


SOURCE_POLICY_PATH = Path(".wikicommit/source-policy.md")


def _normalize_policy_domain(raw: str) -> str:
    """Reduce a hand-written exclude_domains entry to the form _domain_of() yields.

    Entries are written by a human next to a `rejected:` list whose entries are
    full URLs, so `https://example.com/`, `example.com/some/path` and
    `www.example.com` are all plausible spellings of the same intent. Comparing
    them raw against _domain_of()'s output (scheme-less, port-less, www-less)
    would silently match none of them — the domain stays fetchable while the
    file says it is excluded, with nothing anywhere reporting the mismatch.
    """
    value = raw.strip().lower()
    if not value:
        return ""
    # urlparse only fills netloc when it sees an authority; "//" makes a bare
    # host (or a "host/path" entry) parse as one, and a real scheme still works.
    if "://" not in value:
        value = "//" + value.lstrip("/")
    return _domain_of(value)


def policy_exclude_domains(path: Path = SOURCE_POLICY_PATH) -> set[str]:
    """`wikicommit.exclude_domains` from .wikicommit/source-policy.md (Issue #564).

    Where KNOWN_JS_SHELL_DOMAINS holds facts true for every wiki, this holds one
    wiki's own decisions — the two are unioned, never substituted. A repository
    cannot re-enable a domain the built-in list names, because doing so would not
    make it fetchable; it can only add to the list.

    Missing file, unreadable file, unparseable frontmatter, or a non-list value
    all mean "no extra domains". A source-selection policy must not be able to
    break the extraction guard that runs before every URL fetch. Failing open
    silently would be its own trap, though — wikicommit-collect appends to this
    file's `rejected:` list, so one malformed append would switch every
    exclude_domains entry off with nothing to show for it — so a policy file
    that exists but cannot be read is reported on stderr, which leaves the
    stdout contract (`BLOCKED:` / `OK:`) its callers parse untouched.

    Matching is on the exact host: an entry is normalized to _domain_of()'s form,
    but `example.com` does not cover `blog.example.com`. List each host you mean,
    the way KNOWN_JS_SHELL_DOMAINS lists music.youtube.com separately.
    """
    if not path.exists():
        return set()
    frontmatter, error = parse_frontmatter(path)
    if error:
        print(
            f"WARNING: {path}: {error} — wikicommit.exclude_domains is being ignored "
            f"for this check (Issue #564).",
            file=sys.stderr,
        )
        return set()
    if not isinstance(frontmatter, dict):
        return set()
    block = frontmatter.get("wikicommit")
    if not isinstance(block, dict):
        return set()
    domains = block.get("exclude_domains")
    if not isinstance(domains, list):
        return set()
    normalized = {_normalize_policy_domain(d) for d in domains if isinstance(d, str)}
    return {d for d in normalized if d}


def check_domain(url: str) -> int:
    domain = _domain_of(url)
    if domain in KNOWN_JS_SHELL_DOMAINS:
        print(
            f"BLOCKED: {domain} is a known JS-rendering-required domain; "
            f"static fetch (markitdown/curl) has been confirmed to sometimes "
            f"return an empty content shell with no meaningful text. "
            f"(Issue #425)."
        )
        return 1
    if domain in policy_exclude_domains():
        print(
            f"BLOCKED: {domain} is listed under wikicommit.exclude_domains in "
            f".wikicommit/source-policy.md — this wiki has decided against it. "
            f"Edit that file to take it back. (Issue #564)."
        )
        return 1
    print(f"OK: {domain} is not a known JS-shell domain")
    return 0


# Hosts whose real content markitdown can only reach with an extra Python
# package installed, mapped to (package import name, pip install name, what is
# missing without it). Without the package markitdown does not fail or warn —
# it returns the metadata it *can* read and drops the rest, so the pipeline
# runs to completion and records a page whose source URL never supplied the
# content it claims to be based on (Issue #574; the same provenance failure
# Issue #425 identified for x.com, reached by a different route).
#
# Hosts are matched exactly against the normalized host (see _domain_of), so
# every alias a site is reachable under has to be listed. The three hosts below
# were confirmed to produce byte-identical extracted output (transcript
# included), because markitdown picks its converter from the URL it lands on
# after redirects and all three land on https://www.youtube.com/watch?…:
# youtu.be/<id> → …/watch?v=<id>&feature=youtu.be, and m.youtube.com/watch?v=<id>
# → …/watch?app=desktop&v=<id>. music.youtube.com is deliberately *not* here:
# it does not redirect at all, so markitdown's YouTubeConverter never runs for
# it and the package would not help — it is handled by guard B above instead.
#
# Note this is a host-level match: it cannot tell a /watch? URL from a
# /shorts/<id>, /playlist, or channel URL on the same host, which markitdown's
# YouTubeConverter also refuses (same literal-prefix requirement). Guard C
# therefore only certifies "the package this host needs is installed", never
# "this URL will extract completely" — see the extraction-shape check in
# wikicommit-generate's Pass 1 step 6 for the other half.
_FETCH_CAPABILITY_REQUIREMENTS = {
    host: (
        "youtube_transcript_api",
        "youtube-transcript-api",
        "the video's transcript (without it, only the title, keywords, runtime "
        "and description are extracted — the video's actual content is missing)",
    )
    for host in ("youtube.com", "youtu.be", "m.youtube.com")
}


def check_fetch_capability(url: str) -> int:
    domain = _domain_of(url)
    requirement = _FETCH_CAPABILITY_REQUIREMENTS.get(domain)
    if requirement is None:
        print(f"OK: {domain} needs no extra extraction package")
        return 0

    module_name, pip_name, missing_content = requirement
    if importlib.util.find_spec(module_name) is not None:
        print(f"OK: {domain}: {module_name} is installed")
        return 0

    print(
        f"MISSING_PACKAGE: {domain} requires the {pip_name} package to extract "
        f"{missing_content}. Install it with: pip install {pip_name}"
    )
    return 1


def _is_natural_token(token: str) -> bool:
    if any(c in _STRUCTURAL_CHARS for c in token):
        return False
    if token.count('"') > 1 or "`" in token:
        return False
    core = token.strip("[]()*_.,:!?~|\\/'\"")
    if len(core) < 2:
        return False
    alpha_count = sum(1 for c in core if c.isalpha())
    return alpha_count / len(core) >= 0.7


def _tokenize(text: str) -> list[tuple[str, str]]:
    """Split text into (kind, token) pairs, where kind is "url" or "word".

    URLs are cut out at their own boundaries *before* whitespace splitting
    (Issue #562). Splitting on whitespace alone is wrong for languages without
    inter-word spaces: in Japanese, running prose and an adjacent
    percent-encoded link target fuse into one enormous token, and since a URL
    never counts as prose, the fused token took the prose down with it. In a
    space-delimited language the URL is already its own token, so cutting at
    URL boundaries changes nothing there.
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    for match in _URL_RE.finditer(text):
        tokens.extend(("word", t) for t in text[pos:match.start()].split())
        tokens.append(("url", match.group(0)))
        pos = match.end()
    tokens.extend(("word", t) for t in text[pos:].split())
    return tokens


def _density_report(text: str) -> tuple[float, dict[str, int]]:
    """Return the natural-language character ratio and, for the characters
    that did *not* count as prose, a breakdown of what they were.

    The ratio is weighted by character count rather than token count so CJK
    text (which has no inter-word spaces and so forms few, long tokens) isn't
    penalized relative to space-delimited languages; CJK characters carry
    CJK_CHAR_WEIGHT each, and URLs are measured percent-decoded, so that the
    same prose with the same link density scores alike in Japanese and English
    (Issue #562). The breakdown exists so a
    human deciding whether to override a LOW_DENSITY result can see at a glance
    whether the non-prose mass is link targets (a link-dense but genuine page),
    numbers and table pipes (a statistics document — a known limitation of this
    heuristic), or actual markup/script boilerplate.
    """
    buckets = {"link": 0, "numeric": 0, "other": 0}
    natural_weight = 0
    total_weight = 0
    for kind, token in _tokenize(text):
        # A URL is measured percent-decoded (Issue #562): `%E3%81%95` is one
        # character of a page title that the transport encoding inflated to
        # nine, and counting the inflated form made every link to a Japanese
        # page look like nine times as much markup as the same link to an
        # English one.
        weight = _weight(unquote(token)) if kind == "url" else _weight(token)
        total_weight += weight
        if kind == "url":
            buckets["link"] += weight
            continue
        if _is_natural_token(token):
            natural_weight += weight
            continue
        core = token.strip("[]()*_.,:!?~|\\/'\"")
        numeric_count = sum(1 for c in core if c in _NUMERIC_CHARS)
        if core and numeric_count / len(core) >= 0.7:
            buckets["numeric"] += weight
        else:
            buckets["other"] += weight
    if total_weight == 0:
        return 0.0, buckets
    return natural_weight / total_weight, buckets


def _format_breakdown(buckets: dict[str, int]) -> str:
    total = sum(buckets.values())
    if total == 0:
        return "non-prose breakdown: none"
    return (
        "non-prose breakdown: "
        f"links {buckets['link'] / total:.0%}, "
        f"numbers/tables {buckets['numeric'] / total:.0%}, "
        f"other markup {buckets['other'] / total:.0%}"
    )


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

    ratio, buckets = _density_report(text)
    if ratio < LOW_DENSITY_THRESHOLD:
        print(
            f"LOW_DENSITY: {label} (natural-language character ratio: "
            f"{ratio:.2f}, threshold: {LOW_DENSITY_THRESHOLD}) — extracted "
            f"text looks like boilerplate/markup rather than real content. "
            f"{_format_breakdown(buckets)}."
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

    p_capability = sub.add_parser(
        "check-fetch-capability",
        help="Check whether the optional package a URL's host needs for full extraction is installed",
    )
    p_capability.add_argument("url")

    p_density = sub.add_parser(
        "check-density",
        help="Check whether extracted text has low information density (reads stdin if <file> is omitted)",
    )
    p_density.add_argument("file", nargs="?", default=None)

    args = parser.parse_args()

    if args.command == "check-domain":
        return check_domain(args.url)
    if args.command == "check-fetch-capability":
        return check_fetch_capability(args.url)
    return check_density(args.file)


if __name__ == "__main__":
    sys.exit(main())
