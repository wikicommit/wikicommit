"""Tests for .wikicommit/scripts/check_raw_html.py"""

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
