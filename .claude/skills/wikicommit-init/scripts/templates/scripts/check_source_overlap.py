#!/usr/bin/env python3
"""Report pages that repeat their source's wording word for word.

Counts the share of a page's words that sit in a run of at least n words (n
characters on a ja/zh page) that also occurs in the extracted text of its
sources. Quotations, code, blockquotes, tables and `## Generation Notes` are
left out of the page first.

Usage:
    python .wikicommit/scripts/check_source_overlap.py [<page> ...]
        [--n 6] [--cjk-n 12] [--threshold 0.2] [--min-words 100]
        [--summarize-missing] [--all-shares]

With no page arguments every entity page is measured.

Output:
    OVERLAP: <page> 37% (786 words; longest: 24 words "...")
    SHARE: <page> 9% (...)        only with --all-shares
    NO_SOURCE_TEXT: <page>        no comparable source has extracted text here
    NO_SOURCE_TEXT: <N> page(s) not measured ...   with --summarize-missing
    SKIPPED_CROSS_LANG: <page> (<lang> page; sources in <langs>)
    OK: no page over the threshold
    SUMMARY: measured=<N>, overlap=<N>, under_min_words=<N>, no_source_text=<N>, cross_lang=<N>

Exit code: always 0 (informational, non-blocking).

The specification is the `check_source_overlap.py` section of WikiCommit's
script specification (ScriptSpec).
"""

import argparse
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter, parse_frontmatter_and_body_text
from _wikilink import ENTITY_DIR, WIKILINK_RE, collect_entity_pages

# The defaults are calibrated; the measurements are in ScriptSpec.
DEFAULT_N = 6
# Not DEFAULT_N characters: six characters of Japanese match an unrelated source
# by chance. Twelve span roughly six words.
DEFAULT_CJK_N = 12
DEFAULT_THRESHOLD = 0.20
# Below this one shared run of a term's name is already 6% of the page. A ja/zh
# page counts characters, and needs twice this many.
DEFAULT_MIN_WORDS = 100

# Languages written without spaces between words. Korean separates words with
# spaces, so Hangul is split into words like any other script.
CJK_LANGS = ("ja", "zh")
# Kana, CJK ideographs (with extension A and the compatibility block) and the
# halfwidth katakana.
_CJK_CHAR = r"぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ"
_TOKEN_RE = re.compile(rf"[{_CJK_CHAR}]|[^\W_{_CJK_CHAR}]+(?:'[^\W_{_CJK_CHAR}]+)*")
_HAS_CJK = re.compile(rf"[{_CJK_CHAR}]")

# Every excluded span is replaced by this, and the text is split on it, so no
# run is counted across a quotation, a code span or a table.
_BREAK = "\n"

# A closing fence is the opening fence's character, at least as many times
# (CommonMark), and a code span closes on a backtick run of exactly the opening
# run's length — the same rules as `_wikilink.py`'s patterns.
_FENCED_RE = re.compile(
    r"^ {0,3}(?P<fence>(?P<ch>[`~])(?P=ch){2,})[^\n]*\n.*?(?:^ {0,3}(?P=fence)(?P=ch)*[ \t]*$|\Z)",
    re.M | re.S,
)
_INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)[^\n]*?(?<!`)\1(?!`)")
_TABLE_OR_QUOTE_LINE_RE = re.compile(r"^ {0,3}(?:\||>).*$", re.M)
_QUOTED_RE = re.compile(r'"[^"\n]*"|“[^”\n]*”|「[^」\n]*」|『[^』\n]*』')
_IMAGE_RE = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
_LINK_RE = re.compile(r"\[([^\]\n]*)\]\([^)\n]*\)")
_URL_RE = re.compile(r"<?https?://[^\s>)]+>?")
_GENERATION_NOTES_RE = re.compile(r"^##\s+Generation Notes\b.*", re.M | re.S)


def _wikilink_text(match: re.Match) -> str:
    display = match.group(3)
    if display and display.strip():
        return display.strip()
    return match.group(2).replace("-", " ").replace("_", " ")


def _plain_links(text: str) -> str:
    text = _IMAGE_RE.sub(_BREAK, text)
    text = WIKILINK_RE.sub(_wikilink_text, text)
    text = _LINK_RE.sub(lambda m: m.group(1), text)
    return _URL_RE.sub(_BREAK, text)


def page_prose(body: str) -> str:
    """The page body reduced to the prose the page wrote itself (step 3)."""
    body = _GENERATION_NOTES_RE.sub("", body)
    body = _FENCED_RE.sub(_BREAK, body)
    body = _INLINE_CODE_RE.sub(_BREAK, body)
    body = _TABLE_OR_QUOTE_LINE_RE.sub(_BREAK, body)
    body = _QUOTED_RE.sub(_BREAK, body)
    return _plain_links(body)


def tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def segments(text: str) -> list[list[str]]:
    """The text's lines as token lists, each a stretch no run may cross."""
    return [t for t in (tokens(line) for line in text.split(_BREAK)) if t]


_GRAMS: dict[tuple[str, int], frozenset] = {}


def _grams_of(text: str, n: int) -> frozenset:
    # Many pages cite one source (every term a post defines), so each source
    # is split once per run.
    if (text, n) not in _GRAMS:
        words = tokens(_plain_links(text))
        _GRAMS[(text, n)] = frozenset(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    return _GRAMS[(text, n)]


def source_grams(texts: list[str], n: int) -> frozenset:
    if len(texts) == 1:
        return _grams_of(texts[0], n)
    return frozenset().union(*(_grams_of(text, n) for text in texts))


class Overlap:
    def __init__(self, share: float, words: int, longest: list[str]) -> None:
        self.share = share
        self.words = words
        self.longest = longest


def measure(page_text: str, src_grams: frozenset, n: int) -> Overlap:
    """Step 5: the share of the page's tokens inside a run of n or more shared tokens."""
    total = hit_count = 0
    longest: list[str] = []
    for seg in segments(page_text):
        hit = [False] * len(seg)
        for i in range(len(seg) - n + 1):
            if tuple(seg[i:i + n]) in src_grams:
                for j in range(i, i + n):
                    hit[j] = True
        total += len(seg)
        hit_count += sum(hit)
        start = None
        for i, h in enumerate([*hit, False]):
            if h and start is None:
                start = i
            elif not h and start is not None:
                if i - start > len(longest):
                    longest = seg[start:i]
                start = None
    return Overlap(hit_count / total if total else 0.0, total, longest)


def _lang_code(value) -> str:
    """A recorded `source.lang` as a lower-case two-letter code, or "" when it
    is not one (`pt-BR` → `pt`). The same reading `convert_wikilinks.py` gives
    the field for the per-language tally."""
    if value is False:
        # YAML 1.1 reads an unquoted `lang: no` (Norwegian) as False.
        return "no"
    if not isinstance(value, str):
        return ""
    code = re.split(r"[-_]", value.strip().lower(), maxsplit=1)[0].strip()
    return code if re.fullmatch(r"[a-z]{2}", code) else ""


class SourceIndex:
    """Every management file's identity → (cache path, recorded `source.lang`,
    retracted), read once per run.

    The identity is `source.url` / `source.path`, and the cache path is the
    management file's path under its tree, whole, under the cache tree — the
    rule `resolve_source_cache_path.py` applies one identifier at a time
    (`locate_url()` / `locate_path()`). That helper scans the tree for every
    call; a run over the whole wiki would read each management file once per
    page that cites it.
    """

    TREES = (
        ("url", Path(".wikicommit/source/url"), Path(".wikicommit/.cache/ingest-fetch")),
        ("path", Path(".wikicommit/source/path"), Path(".wikicommit/.cache/extract-path")),
    )

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.entries: dict[tuple[str, str], tuple[Path, str, bool]] = {}
        for key, mgmt_rel, cache_rel in self.TREES:
            mgmt_root, cache_root = repo_root / mgmt_rel, repo_root / cache_rel
            if not mgmt_root.is_dir():
                continue
            for management_file in sorted(mgmt_root.rglob("*.md")):
                fm, _ = parse_frontmatter(management_file)
                source = fm.get("source") if isinstance(fm, dict) else None
                if not isinstance(source, dict) or not isinstance(source.get(key), str):
                    continue
                self.entries.setdefault((key, source[key].strip()), (
                    cache_root / management_file.relative_to(mgmt_root),
                    _lang_code(source.get("lang")),
                    str(fm.get("status") or "").strip() == "retracted",
                ))

    def text(self, entry: dict) -> tuple[str | None, str]:
        """(the extracted text, the recorded `source.lang` or "") for one
        `sources[]` entry. The text is "" when the source should have text but
        none is on this machine, and None when there is nothing to measure
        against either way — a `type: manual` entry, or a retracted source
        (`check_retracted_sources.py` reports those pages)."""
        kind = entry.get("type")
        key = "url" if kind in ("url", "wikicommit") else "path" if kind == "path" else ""
        identity = entry.get(key) if key else None
        if not isinstance(identity, str) or not identity.strip():
            return None, ""
        identity = identity.strip()
        cache, lang, retracted = self.entries.get((key, identity), (None, "", False))
        if retracted:
            return None, lang
        candidates = [cache] if cache is not None else []
        if key == "path" and Path(identity).suffix.lower() in (".md", ".txt"):
            # Pass 1 reads these as they are and keeps no extraction cache.
            candidates.append(self.repo_root / identity)
        for candidate in candidates:
            if candidate.is_file():
                try:
                    return candidate.read_text(encoding="utf-8", errors="replace"), lang
                except OSError:
                    pass
        return "", lang


def check_page(page: Path, args, index: SourceIndex) -> tuple[str, str]:
    """(result, line) for one page; result is one of overlap, ok, short,
    no_source_text, cross_lang, skipped."""
    try:
        content = page.read_text(encoding="utf-8")
    except OSError as e:
        print(f"WARNING: {page}: could not be read ({e})", file=sys.stderr)
        return "skipped", ""
    fm, _, body = parse_frontmatter_and_body_text(content)
    if not isinstance(fm, dict) or fm.get("status") == "removed":
        return "skipped", ""
    lang = _lang_code(fm.get("lang"))
    if fm.get("translated_from"):
        return "cross_lang", f"SKIPPED_CROSS_LANG: {page} (translated page)"
    sources = fm.get("sources")
    entries = [e for e in sources if isinstance(e, dict)] if isinstance(sources, list) else []

    same, other_langs, missing = [], set(), 0
    for entry in entries:
        text, src_lang = index.text(entry)
        if text is None:
            continue
        if src_lang and lang and src_lang != lang:
            other_langs.add(src_lang)
        elif text:
            same.append(text)
        else:
            missing += 1

    if not same:
        # A source that could be compared but has no text outranks one in
        # another language: the page might have been measurable here.
        if missing:
            return "no_source_text", f"NO_SOURCE_TEXT: {page}"
        if other_langs:
            return "cross_lang", (f"SKIPPED_CROSS_LANG: {page} ({lang or 'unknown'} page; "
                                  f"sources in {', '.join(sorted(other_langs))})")
        return "skipped", ""

    cjk = lang in CJK_LANGS or (not lang and _HAS_CJK.search(body or ""))
    n = args.cjk_n if cjk else args.n
    result = measure(page_prose(body or ""), source_grams(same, n), n)
    joiner = "" if cjk else " "
    shown = joiner.join(result.longest)
    if len(shown) > 120:
        shown = shown[:117] + "..."
    unit = "characters" if cjk else "words"
    line = (f"OVERLAP: {page} {result.share:.0%} ({result.words} {unit}; "
            f"longest: {len(result.longest)} {unit} \"{shown}\")")
    if result.words < (args.min_words * 2 if cjk else args.min_words):
        return "short", line.replace("OVERLAP:", "SHARE:", 1) if args.all_shares else ""
    if result.share > args.threshold:
        return "overlap", line
    return "ok", line.replace("OVERLAP:", "SHARE:", 1) if args.all_shares else ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report pages that reuse their source's wording word for word.")
    parser.add_argument("pages", nargs="*", help="pages to measure (default: every entity page)")
    parser.add_argument("--n", type=int, default=DEFAULT_N,
                        help=f"shortest shared run, in words (default {DEFAULT_N})")
    parser.add_argument("--cjk-n", type=int, default=DEFAULT_CJK_N,
                        help=f"shortest shared run on a ja/zh page, in characters "
                             f"(default {DEFAULT_CJK_N})")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"report a page whose share is over this (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--min-words", type=int, default=DEFAULT_MIN_WORDS,
                        help=f"do not report a page with fewer tokens than this "
                             f"(default {DEFAULT_MIN_WORDS})")
    parser.add_argument("--summarize-missing", action="store_true",
                        help="print one NO_SOURCE_TEXT count instead of one line per page")
    parser.add_argument("--all-shares", action="store_true",
                        help="also print a SHARE: line for every measured page under the "
                             "threshold (for calibrating it)")
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

    index = SourceIndex(Path())
    pages = [Path(p) for p in args.pages] if args.pages else collect_entity_pages(ENTITY_DIR)
    counts = dict.fromkeys(("overlap", "ok", "short", "no_source_text", "cross_lang"), 0)
    missing = 0
    for page in pages:
        result, line = check_page(page, args, index)
        if result in counts:
            counts[result] += 1
        if result == "no_source_text" and args.summarize_missing:
            missing += 1
            continue
        if line:
            print(line)
    if missing:
        print(f"NO_SOURCE_TEXT: {missing} page(s) not measured — none of their sources has "
              "extracted text on this machine")
    measured = counts["overlap"] + counts["ok"] + counts["short"]
    if measured and not counts["overlap"]:
        # Not when nothing was measured: a run that measured no page has not passed.
        print("OK: no page over the threshold")
    print(f"SUMMARY: measured={measured}, overlap={counts['overlap']}, "
          f"under_min_words={counts['short']}, no_source_text={counts['no_source_text']}, "
          f"cross_lang={counts['cross_lang']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
