"""Tests for .wikicommit/scripts/reconcile_ingest_status.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "reconcile_ingest_status.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "reconcile_ingest_status.py"
)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_ingest_file(root: Path, rel_path: str, source_hash: str, status: str, extra_frontmatter: str = "") -> Path:
    mgmt_file = root / ".wikicommit" / "source" / "path" / rel_path
    mgmt_file.parent.mkdir(parents=True, exist_ok=True)
    # Dedent *before* interpolating. `textwrap.dedent` strips the longest common
    # indent across all lines, so a caller-supplied `extra_frontmatter` starting
    # at column 0 would drop the common prefix to "" and leave the whole block
    # indented — which is not frontmatter at all, and the test would then pass
    # because the file parses as having no `status` rather than because the
    # script decided anything. The parameter had no callers until Issue #874.
    frontmatter = textwrap.dedent("""\
        ---
        source:
          type: path
          path: raw/paper.txt
          hash: {source_hash}
        status: {status}
        """).format(source_hash=source_hash, status=status)
    mgmt_file.write_text(frontmatter + extra_frontmatter + "---\n", encoding="utf-8")
    return mgmt_file


def write_page(root: Path, lang: str, type_name: str, slug: str, source_hash: str) -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(
        textwrap.dedent(f"""\
            ---
            title: "Test Page"
            type: "schema:Person"
            lang: {lang}
            sources:
              - type: path
                path: raw/paper.txt
                hash: {source_hash}
            ---

            Body.
            """),
        encoding="utf-8",
    )
    return page


def test_no_ingest_dir(tmp_path):
    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout


def test_pending_with_matching_hash_reconciled(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run(["--today=2026-08-14"], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" in result.stdout
    assert ".wikicommit/entity/ja/Person/yamada-taro.md" in result.stdout
    assert "page: .wikicommit/source/path/paper.md" in result.stdout
    assert "SUMMARY: reconciled=1" in result.stdout

    updated = mgmt_file.read_text(encoding="utf-8")
    assert "status: generated" in updated
    assert 'generated_pages: [".wikicommit/entity/ja/Person/yamada-taro.md"]' in updated
    assert 'last_generated_at: "2026-08-14"' in updated


def test_pending_with_no_match_left_alone(tmp_path):
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_outdated_not_touched_even_with_matching_hash(tmp_path):
    """Critical regression guard: check_ingest_freshness.py deliberately leaves the
    old (page-matching) hash in place when it flags a file outdated — a hash match
    on an outdated file means "was generated before the source changed and still
    needs reprocessing", not "already reconciled". Reconciling it here would mask
    genuine staleness (this was the most serious bug in an earlier prose-based
    version of this fix, per Issue #474's code review)."""
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "outdated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: outdated" in mgmt_file.read_text(encoding="utf-8")


def test_generated_status_not_touched(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "generated")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: generated" in mgmt_file.read_text(encoding="utf-8")


def test_empty_hash_skipped_not_treated_as_wildcard(tmp_path):
    """A pending type:url source registered before Pass 1 fetched it has hash: "" —
    this must never be treated as a match against every page (Issue #474 review)."""
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", '""', "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "RECONCILED:" not in result.stdout
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_failure_reason_section_removed_on_reconcile(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")
    content = mgmt_file.read_text(encoding="utf-8")
    content = content.rstrip("\n") + "\n\n## Failure Reason\n\nSomething went wrong previously.\n"
    mgmt_file.write_text(content, encoding="utf-8")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=1" in result.stdout
    updated = mgmt_file.read_text(encoding="utf-8")
    assert "## Failure Reason" not in updated


def test_multiple_pages_citing_same_hash_all_listed_sorted(tmp_path):
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    write_page(tmp_path, "ja", "Organization", "companya", "sha256:abc123")
    mgmt_file = write_ingest_file(tmp_path, "paper.md", "sha256:abc123", "pending")

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=1" in result.stdout
    updated = mgmt_file.read_text(encoding="utf-8")
    assert (
        'generated_pages: [".wikicommit/entity/ja/Organization/companya.md", '
        '".wikicommit/entity/ja/Person/yamada-taro.md"]' in updated
    )


# ── ポリシー起点の requeue を黙って取り消さない（Issue #874）──────────────────
#
# 新しい requeue Skill は「ポリシー・型テンプレート・生成ルールが変わったので
# Pass 2c をもう一度通したい」ソースを `status: pending` に戻す。ここを素通り
# させると、generate が実行の最後にこのスクリプトを呼んだ時点で `generated` へ
# 書き戻され、**しかも出力は成功系の `RECONCILED:` である**。5 件ガードと
# 組み合わさると 1 回の実行でキューが壊滅する（50 件戻す → 5 件処理 → 残り 45 件が
# generated へ戻り、二度と拾われない）。
#
# 2 つの起点を守るのは別々の条件であり、片方のコードからもう片方は見えない。


def test_a_requeued_source_that_made_pages_is_left_alone(tmp_path):
    """`generated` / `partial` 起点 — 新しい `generated_pages` の条件が守る。

    ページを作ったソースの hash は定義上そのページの `sources[]` に現れるため、
    既存の 3 条件だけでは必ず一致してしまう。
    """
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(
        tmp_path, "paper.md", "sha256:abc123", "pending",
        extra_frontmatter='generated_pages: [".wikicommit/entity/ja/Person/yamada-taro.md"]\n',
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_a_requeued_source_that_made_no_page_is_left_alone(tmp_path):
    """`excluded` 起点 — 既存のハッシュ条件が守る。

    こちらはスイッチを off に戻す経路そのもの（Issue #874 の本題）であり、
    ページを 1 枚も作っていない以上その hash はどのページにも現れない。
    この 1 件が無いと、次に読む人が「除外起点は無防備では」と同じ調査を
    やり直すことになる。
    """
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:other")
    mgmt_file = write_ingest_file(
        tmp_path, "excluded-source.md", "sha256:abc123", "pending",
        extra_frontmatter="generated_pages: []\n",
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_a_requeued_source_excluded_after_making_pages_is_left_alone(tmp_path):
    """3 つ目の requeue 起点 — `last_generated_at` の条件だけが守る。

    ポリシーを厳しくして requeue → generate で全件除外、という一度の往復で到達する。
    Pass 4 step 7 の `excluded` 分岐は `generated_pages` を書かない一方、以前の
    ゆるいポリシーで作られたページはディスクに残り（生成経路にページを消す手段は
    無い）、変わっていない hash を引用し続ける。つまりこのファイルは
    `generated_pages` の条件も hash 一致の条件も**両方すり抜ける** — その状態で
    requeue すると、届かなかった generate の末尾でここが `generated` に書き戻し、
    しかも `RECONCILED:` は成功行なので、キューから消えたことが誰にも見えない。
    """
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(
        tmp_path, "paper.md", "sha256:abc123", "pending",
        extra_frontmatter='last_generated_at: "2026-09-01"\ngenerated_pages: []\n',
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=0" in result.stdout
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")


def test_the_issue_474_case_still_reconciles(tmp_path):
    """条件を狭めた結果、元々救おうとしていた形まで落ちていないこと。

    Issue #474 の対象は「ページは書かれたが、この管理ファイル自身の
    `status` / `generated_pages` が書き戻されなかった」= `generated_pages` が
    空のまま残ったファイルである。
    """
    write_page(tmp_path, "ja", "Person", "yamada-taro", "sha256:abc123")
    mgmt_file = write_ingest_file(
        tmp_path, "paper.md", "sha256:abc123", "pending",
        extra_frontmatter="generated_pages: []\n",
    )

    result = run([], cwd=tmp_path)
    assert result.returncode == 0
    assert "SUMMARY: reconciled=1" in result.stdout
    assert "status: generated" in mgmt_file.read_text(encoding="utf-8")


# ── wikicommit-init template stays in sync with the canonical script (#71〜#75, #231) ──

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")
