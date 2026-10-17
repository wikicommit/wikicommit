#!/usr/bin/env python3
"""Detect raw HTML tags in wiki page body content.

WikiCommit's design commits to embedding local/external images, video files,
and YouTube via standard Markdown image syntax only (`![alt](path-or-url)`,
which Quartz handles natively) — there is no legitimate
need for a wiki page body to contain a raw HTML tag. Quartz's Markdown-to-
HTML pipeline passes raw HTML straight through regardless of
`enableInHtmlEmbed` (`remarkRehype(..., { allowDangerousHtml: true })` is
always on in Quartz core), so an unreviewed page (`review_status: pending`)
that picks up a `<script>`/`<iframe>` tag — whether from an indirect prompt
injection in an ingested source document, or an LLM hallucination — would
execute in a reader's browser as soon as it is auto-merged and published,
before any human reviews it. This script is the merge-time blocking gate
that closes that gap: any raw HTML tag found in page body content is a
blocking ERROR, with no tag allowlist (the design position is "no raw HTML
at all", not "no dangerous HTML" — see the module-level docstring's "known
limitation" note below for what this trades away).

Which parts of the body count as raw HTML is decided by a CommonMark parser
(`markdown-it-py`), not by pattern-matching the text: only the parser's raw
HTML tokens (`html_block` and `html_inline`) are checked. Those are exactly
the spans a Markdown renderer emits as HTML, so the check and the published
page follow the same rules. In particular, content inside fenced
code blocks (of any fence length, closed with up to three spaces of
indentation, as CommonMark allows), indented code blocks and inline code spans
(of any backtick-run length) is not flagged, since Markdown renders that
content as escaped text regardless of `allowDangerousHtml` — a HowTo page that
shows `<script>` as a code example poses no rendering risk and is not
disallowed. A fence that is never closed runs to the end of the document in
CommonMark, so HTML after it is code and is not flagged either.

CommonMark autolinks (`<https://example.com>`, `<user@example.com>`) are not
flagged — they are Pass 3's documented technique for disambiguating a bare
URL from surrounding prose (`.claude/skills/wikicommit-generate/SKILL.md`
Pass 3 step 8), not raw HTML, and the parser reads them as links.

Within a raw HTML token, every open or close tag is reported. An HTML comment,
processing instruction, declaration or CDATA section with no tag in it is not
reported, since a browser renders none of them; a tag inside one is reported
(fail safe). An HTML block that starts like a tag but holds no complete tag is
reported by its first line.

Known limitation: a purely inert tag with no scripting capability (e.g.
`<br>` for a line break inside a table cell) is blocked the same as
`<script>`, since this script intentionally has no tag allowlist to
maintain (an allowlist is exactly the sanitize-list design this script chose
not to build, once the embed styleguide in CLAUDE.md established that no
raw HTML tag has a legitimate use in a wiki page body). Text such as `a<b>c`
outside code is blocked too, because CommonMark itself reads `<b>` there as an
HTML tag and the published page would render it as one. Constructs CommonMark
does not have (Obsidian callouts, math) are parsed as ordinary Markdown, so
HTML inside them is reported.

If `markdown-it-py` is not installed, every run exits 1 with an `ERROR:` on
stderr naming the package (no file is read), so the gate fails closed rather
than passing unchecked pages, and a caller reading stdout for page findings
(`/wikicommit-status`) sees "could not run", not a finding on some page.

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
from _wikilink import ENTITY_DIR, VIEW_DIR

try:
    from markdown_it import MarkdownIt
    from markdown_it.common.html_re import close_tag, open_tag
except ModuleNotFoundError as e:
    _IMPORT_ERROR: ModuleNotFoundError | None = e
else:
    _IMPORT_ERROR = None

IN_GITHUB_ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"

# CommonMark's own open/close tag grammar (the same one the parser uses to
# recognise inline HTML), so a tag name with a hyphen or an attribute value
# holding `>` is reported whole.
TAG_RE = re.compile(f"{open_tag}|{close_tag}") if _IMPORT_ERROR is None else None

# The CommonMark parser, with GFM tables and strikethrough on as the published
# site renders them.
PARSER = MarkdownIt("commonmark").enable(["table", "strikethrough"]) if _IMPORT_ERROR is None else None

# Constructs that open a raw HTML token but are never rendered by a browser:
# comments, declarations and CDATA (`<!`) and processing instructions (`<?`).
_INERT_PREFIXES = ("<!", "<?")


def _html_tokens(tokens):
    """Yield every html_block / html_inline token, including inline children."""
    for tok in tokens:
        if tok.type in ("html_block", "html_inline"):
            yield tok
        if tok.children:
            yield from _html_tokens(tok.children)


def find_raw_html(body: str) -> list[str]:
    """Return the raw HTML tags a CommonMark renderer would emit for body."""
    found: list[str] = []
    for tok in _html_tokens(PARSER.parse(body)):
        content = tok.content
        tags = [m.group(0) for m in TAG_RE.finditer(content)]
        if tags:
            found.extend(tags)
            continue
        stripped = content.strip()
        if not stripped or stripped.startswith(_INERT_PREFIXES):
            continue
        found.append(stripped.splitlines()[0])
    return found


def emit_github_annotation(level: str, file_str: str, message: str) -> None:
    print(f"::{level} file={file_str},title=raw-html::{message}")


def main() -> int:
    if _IMPORT_ERROR is not None:
        print(
            f"ERROR: markdown-it-py is not installed ({_IMPORT_ERROR}); this check cannot run "
            "without it. Install it with: pip install markdown-it-py",
            file=sys.stderr,
        )
        return 1

    repo_root = Path.cwd()
    entity_dir = repo_root / ENTITY_DIR

    if len(sys.argv) > 1:
        target_files: list[Path] = [Path(a) for a in sys.argv[1:]]
    else:
        # Both trees: a view page's body is published the same way and is
        # subject to the same raw-HTML ban. As above, every `.md` on disk is
        # checked — this script's subject is files, not the page graph.
        target_files = sorted(entity_dir.rglob("*.md")) if entity_dir.exists() else []
        view_dir = repo_root / VIEW_DIR
        if view_dir.exists():
            target_files += sorted(view_dir.rglob("*.md"))

    if not target_files:
        print("OK: 0 files checked, 0 errors")
        return 0

    total_errors = 0
    files_checked = 0

    for fp in target_files:
        fp = Path(fp)
        if not fp.exists():
            print(f"ERROR: {fp}: file does not exist", file=sys.stderr)
            total_errors += 1
            continue

        try:
            rel_str = str(fp.relative_to(repo_root))
        except ValueError:
            rel_str = str(fp)

        try:
            content = fp.read_text(encoding="utf-8-sig")
        except OSError as e:
            print(f"ERROR: {rel_str}: could not be read: {e}")
            total_errors += 1
            continue

        files_checked += 1

        _, err, body = parse_frontmatter_and_body_text(content)
        if err:
            # validate_frontmatter.py already reports a malformed frontmatter
            # block as a blocking error; this script only cares about body
            # content, so it just skips a page it cannot split cleanly.
            print(f"WARNING: {rel_str}: frontmatter could not be parsed, so the body check was skipped ({err})")
            continue

        for tag in find_raw_html(body):
            # A tag can span lines; keep each finding on one output line.
            tag = " ".join(tag.split())
            snippet = tag if len(tag) <= 120 else tag[:117] + "..."
            msg = f"raw HTML tag detected: {snippet}"
            print(f"ERROR: {rel_str}: {msg}")
            if IN_GITHUB_ACTIONS:
                emit_github_annotation("error", rel_str, msg)
            total_errors += 1

    print(f"OK: {files_checked} files checked, {total_errors} errors")
    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
