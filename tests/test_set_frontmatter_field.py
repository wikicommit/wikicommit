"""Tests for .wikicommit/scripts/set_frontmatter_field.py (Issue #371)

Shared implementation of the frontmatter single-field rewrite logic that used to
be duplicated independently in wikicommit-review/SKILL.md Step 5 and
review-issue-close-sync.yml.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "set_frontmatter_field.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "set_frontmatter_field.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_page(root: Path, frontmatter: str, body: str = "Body.\n") -> Path:
    page = root / "page.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


# ── --set: replace an existing field ────────────────────────────────────────

def test_set_replaces_existing_field(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\nreview_status: pending\n")

    result = run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    assert result.returncode == 0
    assert "OK:" in result.stdout
    content = page.read_text(encoding="utf-8")
    assert "review_status: reviewed" in content
    assert "title: \"Yamada\"" in content
    assert "Body.\n" in content


# ── --set: append a field that doesn't exist ────────────────────────────────

def test_set_appends_missing_field(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")

    result = run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    assert result.returncode == 0
    content = page.read_text(encoding="utf-8")
    assert "title: \"Yamada\"" in content
    assert "review_status: reviewed" in content


# ── --set: multiple fields in one call ──────────────────────────────────────

def test_set_multiple_fields(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")

    result = run(
        [str(page), "--set", "status=removed", "--set", 'removed_at="2026-07-29"'],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    content = page.read_text(encoding="utf-8")
    assert "status: removed" in content
    assert 'removed_at: "2026-07-29"' in content
    assert "SUMMARY: fields_set=2" in result.stdout


# ── --require: matches current value (quoted or not) → proceeds ────────────

def test_require_matching_value_proceeds(tmp_path):
    page = write_page(tmp_path, "review_status: pending\n")

    result = run(
        [str(page), "--set", "review_status=reviewed", "--require", "review_status=pending"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "review_status: reviewed" in page.read_text(encoding="utf-8")


def test_require_matches_quoted_current_value(tmp_path):
    page = write_page(tmp_path, 'review_status: "pending"\n')

    result = run(
        [str(page), "--set", "review_status=reviewed", "--require", "review_status=pending"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "review_status: reviewed" in page.read_text(encoding="utf-8")


# ── --require: mismatch → SKIP, no changes, exit 0 ──────────────────────────

def test_require_mismatch_skips_without_changes(tmp_path):
    page = write_page(tmp_path, "review_status: reviewed\n")
    original = page.read_text(encoding="utf-8")

    result = run(
        [str(page), "--set", "review_status=reviewed", "--require", "review_status=pending"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "SKIP:" in result.stdout
    assert page.read_text(encoding="utf-8") == original


def test_require_field_absent_skips(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")
    original = page.read_text(encoding="utf-8")

    result = run(
        [str(page), "--set", "review_status=reviewed", "--require", "review_status=pending"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert "SKIP:" in result.stdout
    assert page.read_text(encoding="utf-8") == original


# ── Error cases ──────────────────────────────────────────────────────────────

def test_missing_file_is_error(tmp_path):
    result = run([str(tmp_path / "nonexistent.md"), "--set", "review_status=reviewed"], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_no_frontmatter_block_is_error(tmp_path):
    page = tmp_path / "page.md"
    page.write_text("No frontmatter here.\n", encoding="utf-8")

    result = run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_malformed_set_value_is_error(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")

    result = run([str(page), "--set", "review_status_without_equals_sign"], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_malformed_require_value_is_error(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")

    result = run(
        [str(page), "--set", "review_status=reviewed", "--require", "no_equals_sign"],
        cwd=tmp_path,
    )

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_no_set_flag_is_error(tmp_path):
    page = write_page(tmp_path, "title: \"Yamada\"\n")

    result = run([str(page)], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr


# ── Body text is left untouched (only the frontmatter block is rewritten) ──

def test_body_occurrence_of_key_is_not_rewritten(tmp_path):
    page = write_page(
        tmp_path, "review_status: pending\n",
        body="This page discusses review_status: pending as a concept.\n",
    )

    run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    content = page.read_text(encoding="utf-8")
    assert "review_status: pending as a concept" in content
    assert content.count("review_status: reviewed") == 1


# ── --unset: remove a field (Issue #705) ────────────────────────────────────

def test_unset_removes_existing_field(tmp_path):
    page = write_page(tmp_path, 'title: "Yamada"\nreviewed_by: alice\nlang: ja\n')

    result = run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert result.returncode == 0
    text = page.read_text(encoding="utf-8")
    assert "reviewed_by" not in text
    # 他フィールドと本文は保たれる
    assert 'title: "Yamada"' in text
    assert "lang: ja" in text
    assert text.endswith("---\n\nBody.\n")


def test_unset_absent_field_is_a_noop(tmp_path):
    """存在しないキーに対しては何もしない（冪等）。"""
    page = write_page(tmp_path, 'title: "Yamada"\n')
    before = page.read_bytes()

    result = run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert result.returncode == 0
    assert page.read_bytes() == before, "no-op のはずがファイルが書き換わっています"
    assert "fields_unset=0" in result.stdout


def test_unset_is_idempotent_across_runs(tmp_path):
    page = write_page(tmp_path, 'title: "Yamada"\nreviewed_by: alice\n')

    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)
    after_first = page.read_bytes()
    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert page.read_bytes() == after_first


def test_unset_last_field_leaves_no_blank_line(tmp_path):
    """最終行を削除しても frontmatter に空行が入らないこと。

    FRONTMATTER_RE の group(2) は末尾に改行を含まない前提であり、これを崩すと
    呼び出し側が付け直す改行と合わさって `---` の直前に空行ができる。
    """
    page = write_page(tmp_path, 'title: "Yamada"\nreviewed_by: alice\n')

    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert page.read_text(encoding="utf-8") == '---\ntitle: "Yamada"\n---\n\nBody.\n'


def test_unset_keeps_a_trailing_blank_line_it_did_not_create(tmp_path):
    """中間行の削除が、frontmatter 末尾の空行まで巻き添えに消さないこと。

    frontmatter が空行で終わる場合 FRONTMATTER_RE の group(2) は改行で終わり、
    それは元の書式として正当である。削除後の無条件 rstrip はこれを消してしまう。
    """
    page = tmp_path / "page.md"
    page.write_text('---\nreviewed_by: alice\ntitle: "Yamada"\n\n---\n\nBody.\n', encoding="utf-8")

    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert page.read_text(encoding="utf-8") == '---\ntitle: "Yamada"\n\n---\n\nBody.\n'


def test_unset_rejects_key_value_form(tmp_path):
    """`--unset KEY=VALUE`（兄弟フラグの書式）は no-op ではなくエラーにする。

    黙って通すと「消したはずの reviewed_by が残っている」のに exit 0 になる。
    """
    page = write_page(tmp_path, 'title: "Yamada"\nreviewed_by: alice\n')
    before = page.read_bytes()

    result = run([str(page), "--unset", 'reviewed_by=""'], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr
    assert page.read_bytes() == before


def test_unset_multiple_fields(tmp_path):
    page = write_page(tmp_path, 'title: "Yamada"\nreviewed_by: alice\nexpires_at: "2027-01-01"\n')

    result = run(
        [str(page), "--unset", "reviewed_by", "--unset", "expires_at"], cwd=tmp_path
    )

    assert result.returncode == 0
    text = page.read_text(encoding="utf-8")
    assert "reviewed_by" not in text
    assert "expires_at" not in text
    assert 'title: "Yamada"' in text
    assert "fields_unset=2" in result.stdout


def test_unset_only_is_not_an_error(tmp_path):
    """--set を伴わない --unset 単独の呼び出しが弾かれないこと。"""
    page = write_page(tmp_path, 'reviewed_by: alice\ntitle: "Yamada"\n')

    result = run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "ERROR" not in result.stderr


def test_set_and_unset_apply_together(tmp_path):
    """経路 B が実際に行う呼び出し — review_status を書き、reviewed_by を消す。"""
    page = write_page(tmp_path, "review_status: pending\nreviewed_by: alice\n")

    result = run(
        [str(page), "--set", "review_status=reviewed", "--unset", "reviewed_by"],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    text = page.read_text(encoding="utf-8")
    assert "review_status: reviewed" in text
    assert "reviewed_by" not in text


def test_unset_respects_require_mismatch(tmp_path):
    """--require が一致しなければ --unset も適用されない（呼び出しは原子的）。"""
    page = write_page(tmp_path, "review_status: reviewed\nreviewed_by: alice\n")
    before = page.read_bytes()

    result = run(
        [
            str(page), "--require", "review_status=pending",
            "--set", "review_status=reviewed", "--unset", "reviewed_by",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    assert result.stdout.startswith("SKIP:")
    assert page.read_bytes() == before


def test_unset_respects_require_match(tmp_path):
    page = write_page(tmp_path, "review_status: pending\nreviewed_by: alice\n")

    result = run(
        [
            str(page), "--require", "review_status=pending",
            "--set", "review_status=reviewed", "--unset", "reviewed_by",
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0
    text = page.read_text(encoding="utf-8")
    assert "review_status: reviewed" in text
    assert "reviewed_by" not in text


def test_unset_does_not_touch_body_occurrence(tmp_path):
    page = write_page(
        tmp_path, 'title: "Yamada"\nreviewed_by: alice\n', body="reviewed_by: in body\n"
    )

    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    text = page.read_text(encoding="utf-8")
    assert "reviewed_by: in body" in text
    assert "reviewed_by: alice" not in text


def test_neither_set_nor_unset_is_error(tmp_path):
    page = write_page(tmp_path, "review_status: pending\n")

    result = run([str(page)], cwd=tmp_path)

    assert result.returncode == 1
    assert "--set" in result.stderr and "--unset" in result.stderr


def test_unset_with_empty_key_is_error(tmp_path):
    page = write_page(tmp_path, "review_status: pending\n")

    result = run([str(page), "--unset", "   "], cwd=tmp_path)

    assert result.returncode == 1
    assert "ERROR" in result.stderr


def test_unset_preserves_crlf_line_endings(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes(
        b"---\r\ntitle: \"Yamada\"\r\nreviewed_by: alice\r\nlang: ja\r\n---\r\n\r\nBody.\r\n"
    )

    result = run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert result.returncode == 0
    raw = page.read_bytes()
    assert b"reviewed_by" not in raw
    assert b"\n" not in raw.replace(b"\r\n", b""), "LF が混入しています"
    assert raw == b"---\r\ntitle: \"Yamada\"\r\nlang: ja\r\n---\r\n\r\nBody.\r\n"


def test_unset_preserves_crlf_when_removing_last_field(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes(b"---\r\ntitle: \"Yamada\"\r\nreviewed_by: alice\r\n---\r\n\r\nBody.\r\n")

    run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert page.read_bytes() == b"---\r\ntitle: \"Yamada\"\r\n---\r\n\r\nBody.\r\n"


def test_unset_handles_bom(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes(
        "\ufeff---\ntitle: \"Yamada\"\nreviewed_by: alice\n---\n\nBody.\n".encode("utf-8")
    )

    result = run([str(page), "--unset", "reviewed_by"], cwd=tmp_path)

    assert result.returncode == 0
    text = page.read_text(encoding="utf-8-sig")
    assert "reviewed_by" not in text
    assert 'title: "Yamada"' in text


# ── CRLF / BOM preservation ──────────────────────────────────────────────────

def test_preserves_crlf_line_endings(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes(b"---\r\nreview_status: pending\r\n---\r\n\r\nBody.\r\n")

    run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    raw = page.read_bytes()
    assert b"\r\n" in raw
    assert b"review_status: reviewed" in raw


def test_handles_bom(tmp_path):
    page = tmp_path / "page.md"
    page.write_bytes("﻿---\nreview_status: pending\n---\n\nBody.\n".encode("utf-8"))

    result = run([str(page), "--set", "review_status=reviewed"], cwd=tmp_path)

    assert result.returncode == 0
    assert "review_status: reviewed" in page.read_text(encoding="utf-8-sig")


# ── Template mirror stays byte-identical (drift prevention, #71-74 pattern) ─

def test_template_copy_matches_canonical():
    assert TEMPLATE_SCRIPT.read_bytes() == SCRIPT.read_bytes()
