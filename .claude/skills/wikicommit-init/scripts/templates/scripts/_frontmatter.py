"""Shared YAML frontmatter parsing for convert_wikilinks.py, check_wikilinks.py,
check_orphans.py, check_translation_status.py, validate_frontmatter.py
(Issue #212), and check_expires.py, check_ingest_freshness.py, search_index.py
(Issue #231).

Previously each script carried its own copy of the `---\\n...\\n---` extraction,
which had drifted apart in ways that were real bugs rather than harmless style
differences:
- BOM handling: some scripts read with `utf-8-sig`, others with plain `utf-8`,
  so a BOM-prefixed page (as some Windows editors write) silently failed
  frontmatter detection in half the scripts.
- Non-dict YAML: `yaml.safe_load(...) or {}` returns the parsed value
  unchanged when it is a non-empty non-mapping (e.g. a page whose frontmatter
  is a YAML list), so callers that then do `fm.get(...)` on it crash instead
  of reporting a clean error.
- Empty-block detection: a regex-based `^---\\n(.*?)\\n---\\n?` extraction (used
  by 4 of the 5 scripts pre-consolidation) never matches a truly empty block
  (`---\\n---\\n`, i.e. zero content lines between the delimiters), because
  there is no second `\\n` separating the two `---` lines for `(.*?)` to sit
  between. That's harmless in the 4 scripts that treated "no match" as "no
  frontmatter" (both give back `{}` anyway), but validate_frontmatter.py's
  own pre-consolidation implementation used a line-scan instead and handled
  this case correctly, distinguishing it from a genuinely unterminated block.
  This module keeps that line-scan approach so the stricter validate_frontmatter.py
  contract (unterminated block *is* a reportable error) stays correct.

Consolidating here follows the same precedent as _wikilink.py (Issue #114):
one implementation that every script imports, instead of divergent copies
that can only be kept in sync by discipline.
"""

from functools import lru_cache
from pathlib import Path

import yaml


def _split_frontmatter(content: str) -> tuple[dict | None, str, str]:
    """Core line-scan shared by parse_frontmatter_text() and
    parse_frontmatter_and_body_text(). The third element is `content` with
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
        return None, "frontmatter の終端 `---` が見つかりません", content

    body = "\n".join(lines[end_idx + 1:])

    try:
        fm = yaml.safe_load("\n".join(lines[1:end_idx]))
    except yaml.YAMLError as e:
        return None, f"frontmatter の YAML パースに失敗しました: {e}", body

    if fm is None:
        return {}, "", body
    if not isinstance(fm, dict):
        return None, "frontmatter がマッピング形式ではありません", body
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


def parse_frontmatter(path: Path) -> tuple[dict | None, str]:
    """Read path and parse its YAML frontmatter block. See parse_frontmatter_text()."""
    try:
        content = path.read_text(encoding="utf-8-sig")
    except OSError as e:
        return None, f"ファイルを読み込めませんでした: {e}"
    return parse_frontmatter_text(content)


@lru_cache(maxsize=None)
def parse_frontmatter_cached(path: Path) -> tuple[dict | None, str]:
    """Cached variant of parse_frontmatter(), for callers that resolve the
    same page's frontmatter many times in one run.

    check_wikilinks.py and convert_wikilinks.py both call this once per
    WikiLink *occurrence* (via is_removed() / get_lang()), and many links
    across many files can point at the same target page, so without caching
    a popular page gets re-read and re-parsed once per occurrence (Issue
    #232). Consolidated here (Issue #266) after the two scripts had grown
    independent copies of the same `@lru_cache` wrapper.

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
