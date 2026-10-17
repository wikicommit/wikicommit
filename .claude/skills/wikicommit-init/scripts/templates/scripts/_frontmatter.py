"""Shared YAML frontmatter parsing for the scripts that read a page's
frontmatter (convert_wikilinks.py, check_wikilinks.py, validate_frontmatter.py,
search_index.py and the others that import it).

Separate copies of the `---\\n...\\n---` extraction drift apart in ways that
are real bugs rather than harmless style differences:
- BOM handling: a script reading with plain `utf-8` rather than `utf-8-sig`
  silently fails frontmatter detection on a BOM-prefixed page (as some Windows
  editors write).
- Non-dict YAML: `yaml.safe_load(...) or {}` returns the parsed value
  unchanged when it is a non-empty non-mapping (e.g. a page whose frontmatter
  is a YAML list), so callers that then do `fm.get(...)` on it crash instead
  of reporting a clean error.
- Empty-block detection: a regex-based `^---\\n(.*?)\\n---\\n?` extraction
  never matches a truly empty block (`---\\n---\\n`, i.e. zero content lines
  between the delimiters), because there is no second `\\n` separating the two
  `---` lines for `(.*?)` to sit between. That is harmless where "no match"
  means "no frontmatter" (both give back `{}` anyway), but not for
  validate_frontmatter.py, which reports an unterminated block as an error.
  This module uses a line-scan, which tells an empty block from a genuinely
  unterminated one, so that stricter contract stays correct.

So, as with _wikilink.py, there is one implementation that every script
imports, instead of divergent copies that can only be kept in sync by
discipline.
"""

from functools import lru_cache
from pathlib import Path

import yaml


def _split_frontmatter(content: str, loader: type = yaml.SafeLoader) -> tuple[dict | None, str, str]:
    """Core line-scan shared by parse_frontmatter_text(),
    parse_frontmatter_and_body_text() and parse_frontmatter_untyped_text()
    (which passes `loader`). The third element is `content` with
    any frontmatter block stripped off (best-effort: it falls back to the
    original `content` when there is no block at all, or when a missing
    terminator means the body boundary can't be located)."""
    if not content.startswith("---"):
        return {}, "", content

    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.rstrip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return None, "frontmatter has no closing `---`", content

    body = "\n".join(lines[end_idx + 1:])

    try:
        fm = yaml.load("\n".join(lines[1:end_idx]), Loader=loader)
    except yaml.YAMLError as e:
        return None, f"frontmatter is not valid YAML: {e}", body

    if fm is None:
        return {}, "", body
    if not isinstance(fm, dict):
        return None, "frontmatter is not a mapping", body
    return fm, "", body


def parse_frontmatter_text(content: str) -> tuple[dict | None, str]:
    """Parse already-read page text for its YAML frontmatter block.

    Returns ({}, "") when the file has no frontmatter block at all (not an
    error: plenty of non-wiki .md files have none), including a block with
    zero content lines (`---\\n---\\n`). Returns (dict, "") on a successful
    parse of a mapping. Returns (None, error_message) when a frontmatter
    block is opened but never closed, the YAML is malformed, or it parses to
    something other than a mapping.
    """
    fm, err, _ = _split_frontmatter(content)
    return fm, err


def parse_frontmatter_and_body_text(content: str) -> tuple[dict | None, str, str]:
    """Like parse_frontmatter_text(), but also returns the body text with the
    frontmatter block stripped off, for callers (search_index.py) that index
    the frontmatter fields and the body text separately.
    """
    return _split_frontmatter(content)


def parse_frontmatter_untyped_text(content: str) -> tuple[dict | None, str]:
    """Like parse_frontmatter_text(), but read with yaml.BaseLoader, which
    resolves no scalar to a bool, number or date: every scalar is the string as
    written. For a caller that has to tell apart spellings safe_load folds into
    one value (convert_wikilinks.py's `source.lang`, where YAML 1.1 reads `no`,
    `off` and `false` all as False)."""
    fm, err, _ = _split_frontmatter(content, yaml.BaseLoader)
    return fm, err


def parse_frontmatter(path: Path) -> tuple[dict | None, str]:
    """Read path and parse its YAML frontmatter block. See parse_frontmatter_text()."""
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        return None, f"could not be read: {e}"
    return parse_frontmatter_text(content)


@lru_cache(maxsize=None)
def parse_frontmatter_cached(path: Path) -> tuple[dict | None, str]:
    """Cached variant of parse_frontmatter(), for callers that resolve the
    same page's frontmatter many times in one run.

    check_wikilinks.py and convert_wikilinks.py both call this once per
    WikiLink *occurrence* (via is_removed() / get_lang()), and many links
    across many files can point at the same target page, so without caching
    a popular page gets re-read and re-parsed once per occurrence. It lives
    here so the two scripts share one `@lru_cache` wrapper rather than each
    keeping its own copy.

    Caches only the (dict, error) parse result, not anything a caller does
    with `err` — check_wikilinks.py prints a WARNING built from it on every
    call, so a malformed page still gets one WARNING per referencing
    occurrence rather than only on the first.

    Other _frontmatter.py callers (check_orphans.py, etc.) parse each page
    exactly once per run via a single directory walk, so they have no need
    for this and keep calling parse_frontmatter() directly.
    """
    return parse_frontmatter(path)


def parse_frontmatter_or_warn(path: Path) -> dict:
    """Read path and parse its YAML frontmatter block, printing a WARNING and
    falling back to {} on any parse failure instead of surfacing the error.

    For callers (check_wikilinks.py, check_translation_status.py) that
    only need a best-effort dict and treat a parse failure the same as "no
    frontmatter" — as opposed to validate_frontmatter.py and check_orphans.py,
    which need the raw (dict | None, error) contract of parse_frontmatter()
    to report field-level errors or reuse already-read file content.
    """
    fm, err = parse_frontmatter(path)
    if err:
        print(f"WARNING: {path}: {err}")
        return {}
    return fm
