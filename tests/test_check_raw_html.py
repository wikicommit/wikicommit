"""Tests for .wikicommit/scripts/check_raw_html.py"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "check_raw_html.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "check_raw_html.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run check_raw_html.py with args in cwd and return the result."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, body: str) -> Path:
    """Write a minimal wiki page with the given body and return its path."""
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    frontmatter = (
        f'title: "{slug}"\n'
        f"lang: {lang}\n"
        f'type: "schema:{type_name}"\n'
        "review_status: pending\n"
        "sources:\n"
        '  - type: manual\n'
        '    author: "test"\n'
        '    created_at: "2026-01-01"\n'
    )
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


# ── Blocking detections ──────────────────────────────────────────────────

def test_script_tag_is_blocking_error(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Body text.\n\n<script>alert(1)</script>\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout
    assert "<script>" in result.stdout
    assert "</script>" in result.stdout


def test_iframe_tag_is_blocking_error(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", 'See <iframe src="https://evil.example/"></iframe> here.\n')
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "ERROR" in result.stdout


def test_inert_tag_is_also_blocking_error(tmp_path):
    """No allowlist by design (docs/DesignDoc-publish.md §8.6) — even a harmless
    tag like <br> is disallowed, since the point is "no raw HTML", not "no
    dangerous HTML"."""
    write_page(tmp_path, "ja", "Person", "yamada-taro", "line one<br>line two\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<br>" in result.stdout


def test_multiple_files_report_multiple_errors(tmp_path):
    write_page(tmp_path, "ja", "Person", "a", "<script>bad()</script>\n")
    write_page(tmp_path, "ja", "Person", "b", "<div>bad</div>\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    assert result.stdout.count("ERROR:") >= 3  # <script>, </script>, <div>, </div>


# ── Non-detections ───────────────────────────────────────────────────────

def test_clean_page_passes(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Body text with no HTML at all.\n")
    result = run([], tmp_path)
    assert result.returncode == 0
    assert "ERROR" not in result.stdout
    assert "OK: 1 files checked, 0 errors" in result.stdout


def test_markdown_image_syntax_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "![alt](https://example.com/image.jpg)\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_wikilink_syntax_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "See [[Organization/companya]] for details.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_https_autolink_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Visit <https://example.com/article> for more.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_mailto_autolink_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Contact <mailto:foo@example.com>.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_email_autolink_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Contact <foo@example.com> directly.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_inequality_with_spaces_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "a < b and c > d in the formula.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


def test_html_in_fenced_code_block_is_not_flagged(tmp_path):
    body = "Example:\n\n```html\n<script>document.write('hi')</script>\n```\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 0


def test_html_in_tilde_fenced_code_block_is_not_flagged(tmp_path):
    body = "Example:\n\n~~~html\n<iframe src=\"x\"></iframe>\n~~~\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 0


def test_html_in_inline_code_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "HowTo", "example", "Use `<script>` to add a script tag.\n")
    result = run([], tmp_path)
    assert result.returncode == 0


# ── Code ranges follow CommonMark, not a regex (Issue #1322) ──────────────
#
# Each of these used to be blanked out as "code" by a regex that did not
# follow CommonMark's rules for where code ends, so the <script> after it
# passed the gate while micromark rendered it as live HTML.

def test_script_after_four_backtick_fence_holding_three_backtick_line_is_flagged(tmp_path):
    body = "````\n```\n````\n\n<script>alert(1)</script>\n\n```\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<script>" in result.stdout


def test_script_after_fence_closed_with_indented_marker_is_flagged(tmp_path):
    body = "```\ncode\n   ```\n\n<script>alert(1)</script>\n\n```\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<script>" in result.stdout


def test_script_after_four_tilde_fence_holding_three_tilde_line_is_flagged(tmp_path):
    body = "~~~~\n~~~\n~~~~\n\n<script>alert(1)</script>\n\n~~~\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<script>" in result.stdout


def test_script_after_double_backtick_code_span_is_flagged(tmp_path):
    body = "Run ``a`b`` <script>alert(1)</script> now.\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<script>" in result.stdout


def test_howto_showing_a_fence_inside_a_longer_fence_passes(tmp_path):
    body = (
        "To show a code block, wrap it in a longer fence:\n\n"
        "````markdown\n```python\nprint(1)\n```\n````\n\n"
        "Then continue with prose.\n"
    )
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 0, result.stdout


def test_html_in_double_backtick_code_span_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "HowTo", "example", "Write ``<a href=`x`>`` for a link.\n")
    result = run([], tmp_path)
    assert result.returncode == 0, result.stdout


def test_html_after_unclosed_fence_is_code_and_not_flagged(tmp_path):
    """CommonMark runs an unclosed fence to the end of the document, so the
    renderer escapes the <script> — the old regex flagged it only because it
    could not find a closing fence (Issue #1322 changed this expectation)."""
    body = "```\n<script>alert(1)</script>\n"
    write_page(tmp_path, "ja", "HowTo", "example", body)
    result = run([], tmp_path)
    assert result.returncode == 0, result.stdout


def test_hyphenated_tag_with_event_handler_is_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "x <my-el onmouseover=alert(1)> y\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<my-el onmouseover=alert(1)>" in result.stdout


def test_script_in_block_quote_is_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "> <script>alert(1)</script>\n")
    result = run([], tmp_path)
    assert result.returncode == 1


def test_tag_in_table_cell_is_flagged_but_code_in_cell_is_not(tmp_path):
    body = "| a | b |\n|---|---|\n| x<br>y | `<i>` |\n"
    write_page(tmp_path, "ja", "Person", "yamada-taro", body)
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "<br>" in result.stdout
    assert "<i>" not in result.stdout


def test_html_comment_without_tag_is_not_flagged(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "<!-- note -->\n\ntext <!-- x --> y\n")
    result = run([], tmp_path)
    assert result.returncode == 0, result.stdout


def test_missing_markdown_it_fails_closed(tmp_path):
    """Without the parser the gate must block, not pass pages unchecked."""
    shadow = tmp_path / "shadow" / "markdown_it"
    shadow.mkdir(parents=True)
    (shadow / "__init__.py").write_text(
        "raise ModuleNotFoundError(\"No module named 'markdown_it'\", name='markdown_it')\n",
        encoding="utf-8",
    )
    write_page(tmp_path, "ja", "Person", "yamada-taro", "Nothing here.\n")
    env = {**os.environ, "PYTHONPATH": str(shadow.parent)}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, cwd=tmp_path, env=env, check=False,
    )
    assert result.returncode == 1
    # On stderr, like validate_frontmatter.py's "could not run": stdout carries
    # only page findings, so /wikicommit-status does not count this as one.
    assert "ERROR:" not in result.stdout
    assert "ERROR:" in result.stderr
    assert "pip install markdown-it-py" in result.stderr


def test_multiline_tag_is_reported_on_one_line(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "text <img src=x\nonerror=alert(1)> more\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    errors = [line for line in result.stdout.splitlines() if line.startswith("ERROR:")]
    assert len(errors) == 1
    assert errors[0].endswith("<img src=x onerror=alert(1)>")


# ── File targeting ───────────────────────────────────────────────────────

def test_no_args_scans_whole_wiki_dir(tmp_path):
    write_page(tmp_path, "ja", "Person", "clean", "Nothing here.\n")
    write_page(tmp_path, "ja", "Person", "dirty", "<script>bad()</script>\n")
    result = run([], tmp_path)
    assert result.returncode == 1
    assert "OK: 2 files checked" in result.stdout


def test_explicit_args_only_check_given_files(tmp_path):
    clean = write_page(tmp_path, "ja", "Person", "clean", "Nothing here.\n")
    write_page(tmp_path, "ja", "Person", "dirty", "<script>bad()</script>\n")
    result = run([str(clean.relative_to(tmp_path))], tmp_path)
    assert result.returncode == 0
    assert "OK: 1 files checked, 0 errors" in result.stdout


def test_no_wiki_dir_and_no_args_is_clean_ok(tmp_path):
    result = run([], tmp_path)
    assert result.returncode == 0
    assert "OK: 0 files checked, 0 errors" in result.stdout


def test_malformed_frontmatter_warns_and_skips_instead_of_erroring(tmp_path):
    page_dir = tmp_path / ".wikicommit" / "entity" / "ja" / "Person"
    page_dir.mkdir(parents=True)
    page = page_dir / "broken.md"
    page.write_text("---\ntitle: [unterminated\n\n<script>bad()</script>\n", encoding="utf-8")
    result = run([str(page.relative_to(tmp_path))], tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stdout


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75 pattern) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
