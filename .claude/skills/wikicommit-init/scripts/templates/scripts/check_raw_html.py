#!/usr/bin/env python3
"""Detect raw HTML tags in wiki page body content.

WikiCommit's design commits to embedding local/external images, video files,
and YouTube via standard Markdown image syntax only (`![alt](path-or-url)`;
see CLAUDE.md and docs/DesignDoc-publish.md §8.6) — there is no legitimate
need for a wiki page body to contain a raw HTML tag. Quartz's Markdown-to-
HTML pipeline passes raw HTML straight through regardless of
`enableInHtmlEmbed` (`remarkRehype(..., { allowDangerousHtml: true })` is
always on in Quartz core), so an unreviewed page (`review_status: pending`)
that picks up a `<script>`/`<iframe>` tag — whether from an indirect prompt
injection in an ingested source document, or an LLM hallucination — would
execute in a reader's browser as soon as it is auto-merged and published,
before any human reviews it (Issue #377). This script is the merge-time
blocking gate that closes that gap: any raw HTML tag found in page body
content is a blocking ERROR, with no tag allowlist (the design position is
"no raw HTML at all", not "no dangerous HTML" — see the module-level
docstring's "known limitation" note below for what this trades away).

Content inside fenced code blocks (``` / ~~~) and inline code spans (`...`)
is excluded from detection, since Markdown renders that content as escaped
text (not a raw-HTML AST node) regardless of `allowDangerousHtml` — a HowTo
page that shows `<script>` as a code example poses no rendering risk and is
not disallowed.

CommonMark autolinks (`<https://example.com>`, `<user@example.com>`) are not
flagged — they are Pass 3's documented technique for disambiguating a bare
URL from surrounding prose (`.claude/skills/wikicommit-generate/SKILL.md`
Pass 3 step 8), not raw HTML. They are naturally excluded because an HTML
tag name in this script's pattern cannot be followed by `:` or `@`.

Known limitation: a purely inert tag with no scripting capability (e.g.
`<br>` for a line break inside a table cell) is blocked the same as
`<script>`, since this script intentionally has no tag allowlist to
maintain (an allowlist is exactly the sanitize-list design this Issue chose
not to build, once the embed styleguide in CLAUDE.md established that no
raw HTML tag has a legitimate use in a wiki page body). A false positive on
`a<b>c` style inequality chains outside of code fences is possible for the
same reason; this is treated as an acceptable trade-off for a blocking
security gate that fails safe.

Usage:
    python .wikicommit/scripts/check_raw_html.py               # all files
    python .wikicommit/scripts/check_raw_html.py <path>...     # specific files

Exit code: 0 = no ERROR, 1 = at least one ERROR.
"""

import os
import re
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text
from _wikilink import ENTITY_DIR

IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

FENCE_RE = re.compile(r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$", re.DOTALL | re.MULTILINE)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
HTML_TAG_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]*)?/?>")


def _blank(match: re.Match) -> str:
    """Replace a matched span with spaces, preserving newlines, so byte
    offsets of any remaining text are unaffected."""
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_code_zones(body: str) -> str:
    """Blank out fenced code blocks and inline code spans before scanning,
    since Markdown escapes their content rather than emitting raw HTML."""
    body = FENCE_RE.sub(_blank, body)
    body = INLINE_CODE_RE.sub(_blank, body)
    return body


def find_raw_html(body: str) -> list[str]:
    scanned = strip_code_zones(body)
    return [m.group(0) for m in HTML_TAG_RE.finditer(scanned)]


def emit_github_annotation(level: str, file_str: str, message: str) -> None:
    print(f"::{level} file={file_str},title=raw-html::{message}")


def main() -> int:
    repo_root = Path.cwd()
    entity_dir = repo_root / ENTITY_DIR

    if len(sys.argv) > 1:
        target_files: list[Path] = [Path(a) for a in sys.argv[1:]]
    else:
        if not entity_dir.exists():
            print("OK: 0 files checked, 0 errors")
            return 0
        target_files = sorted(entity_dir.rglob("*.md"))

    if not target_files:
        print("OK: 0 files checked, 0 errors")
        return 0

    total_errors = 0
    files_checked = 0

    for fp in target_files:
        fp = Path(fp)
        if not fp.exists():
            print(f"ERROR: {fp}: ファイルが存在しません", file=sys.stderr)
            total_errors += 1
            continue

        try:
            rel_str = str(fp.relative_to(repo_root))
        except ValueError:
            rel_str = str(fp)

        try:
            content = fp.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"ERROR: {rel_str}: ファイルを読み込めませんでした: {e}")
            total_errors += 1
            continue

        files_checked += 1

        _, err, body = parse_frontmatter_and_body_text(content)
        if err:
            # validate_frontmatter.py already reports a malformed frontmatter
            # block as a blocking error; this script only cares about body
            # content, so it just skips a page it cannot split cleanly.
            print(f"WARNING: {rel_str}: frontmatter を解析できないため本文チェックをスキップします ({err})")
            continue

        for tag in find_raw_html(body):
            snippet = tag if len(tag) <= 120 else tag[:117] + "..."
            msg = f"生 HTML タグが検出されました: {snippet}"
            print(f"ERROR: {rel_str}: {msg}")
            if IN_GITHUB_ACTIONS:
                emit_github_annotation("error", rel_str, msg)
            total_errors += 1

    print(f"OK: {files_checked} files checked, {total_errors} errors")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
