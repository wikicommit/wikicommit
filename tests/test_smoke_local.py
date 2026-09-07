"""GitHub 不要のローカル完結スモークテスト（Issue #92 / DesignDoc-TestSpec.md T1）

Issue #86（`.claude/skills/`・`.wikicommit/{config.yml,schema/,scripts/}` が一度も
コミットされない配布漏れ）のような不具合は、かつて GitHub 上に使い捨てリポジトリを作り
Actions・Pages 公開まで待つ重量級 E2E でしか検知できないものと考えられていた。実際には
その E2E は運用されず、この種の不具合を実際に見つけたのはパイロット運用だった
（Issue #556）ため、E2E は Issue #714 で廃止した。このテストは
install.sh → wikicommit-init → SKILL.md 記載の初回コミット手順 → wikicommit-generate 相当
（add_source.py 呼び出し。ページ生成は LLM 呼び出しのため除外しダミーページで代替）→
wikicommit-merge のコミット手順相当（品質チェック・GitHub API 呼び出しは除外）を、
一時ディレクトリの使い捨てローカル git リポジトリ上で実行し、同種の配布漏れが
GitHub 到達性なしに CI（PR 単位）で即検知できることを保証する。

Issue #106（ingest 対象の実ソースファイル自体のコミットタイミングが未定義だった問題）の
恒久対応として、wikicommit-merge SKILL.md ステップ 2 の 3. が定義する
「未追跡の実ソースファイルのみを bulk update コミットに含める」ロジックも検証する。
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
INIT_PY = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "init.py"
PRINT_NEXT_STEPS_PY = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "print_next_steps.py"
ADD_SOURCE_PY = REPO_ROOT / ".claude" / "skills" / "wikicommit-generate" / "scripts" / "add_source.py"

# tests/test_check_translation_status.py と同じ理由: 開発者/CI ランナーの
# グローバル・システム git 設定（gpgsign・hooksPath 等）から使い捨てリポジトリを隔離する。
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def git(args: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, env=_GIT_ENV, text=True, capture_output=True, **kwargs)


def init_git_repo(root: Path) -> None:
    git(["init", "-q"], root, check=True)
    git(["config", "user.email", "test@example.com"], root, check=True)
    git(["config", "user.name", "Test"], root, check=True)


def tracked_files(cwd: Path) -> list[str]:
    return git(["ls-files"], cwd, check=True).stdout.splitlines()


def _git_status_porcelain(cwd: Path, args: list[str]) -> str:
    """`git -c core.quotePath=false status --porcelain <args>` を実行し stdout を返す共通ヘルパー。

    `core.quotePath=false` は本ファイル内のすべての `git status --porcelain` 呼び出しで
    共通して付与する（Issue #115。SKILL.md の同じ注記と対応）。デフォルト設定では非 ASCII
    文字（日本語ファイル名等）を含むパスがダブルクォート + 8 進数エスケープされて出力される。
    """
    return git(["-c", "core.quotePath=false", "status", "--porcelain", *args], cwd, check=True).stdout


def changed_paths(cwd: Path, pathspec: str) -> list[str]:
    """`git status --porcelain` の出力から、削除以外の変更ファイルのパスを取り出す。

    wikicommit-merge SKILL.md ステップ 2 の記述（先頭 2 文字のステータスコードと
    半角スペースを取り除く。リネームは `->` の右側のみ。ステータスコードに `D`
    〔削除〕を含む行はワーキングツリー上に実体がないため対象外）と同じ解析ルール。
    """
    out = _git_status_porcelain(cwd, ["--", pathspec])
    paths = []
    for line in out.splitlines():
        if not line:
            continue
        status, rest = line[:2], line[3:]
        if "D" in status:
            continue
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[1]
        paths.append(rest)
    return paths


def classify_source_status(cwd: Path, source_path: str) -> str:
    """ソース管理ファイルが参照する `source.path` の git 追跡状態を判定する。

    wikicommit-merge SKILL.md ステップ 2 の 3.（Issue #115 / #368）と同じロジック:
    まず `source.path` がワーキングツリー上に実在するかを確認する（Issue #368）。
    `git status --porcelain` は working tree 上に見つかったパスしか報告しないため、
    登録後に削除された `source.path` は「追跡済み・変更なし」ケースと全く同じ
    空文字列を返し、git status の出力だけでは区別できない。実在確認を先に行う
    ことでこの2ケースを切り分ける。

    実在する場合のみ `-c core.quotePath=false` と `--ignored` を付与し、pathspec
    には `:(literal)` プレフィックスを付与して git status を実行する。`:(literal)`
    がない場合、`source.path` が `[`, `]`, `*`, `?` 等の glob メタ文字を含むと
    pathspec として解釈され、対象ファイルが存在しなくても同ディレクトリの無関係な
    別ファイルに誤マッチしうる。`--ignored` がない場合、`.gitignore` で除外された
    ファイルの出力は「追跡済み・変更なし」ケースと同じ空文字列になり区別できない。

    戻り値: "missing"（ワーキングツリー上に実在しない）/ "new"（未追跡・コミット
    対象）/ "ignored"（.gitignore 除外）/ "tracked"（追跡済み。変更の有無を問わない）
    """
    if not (cwd / source_path).exists():
        return "missing"
    status = _git_status_porcelain(cwd, ["--ignored", "--", f":(literal){source_path}"])
    if status.startswith("??"):
        return "new"
    if status.startswith("!!"):
        return "ignored"
    return "tracked"


_INGEST_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def discover_new_source_files(cwd: Path) -> list[str]:
    """wikicommit-merge SKILL.md ステップ 2 の 3.（Issue #106）と同じロジックで、
    bulk update コミットに含めるべき ingest 対象の実ソースファイルを検出する。

    変更された ソース管理ファイル（削除は `changed_paths` が除外済み）の
    source.type: path / source.path を読み取り、`classify_source_status` が
    "new"（未追跡）と判定した場合のみ対象とする。既に追跡済みの既存ファイル
    （例: src/auth.py 相当）や、追跡済みだが未コミットの変更があるファイル、
    `.gitignore` で除外されているファイルは対象外とする。frontmatter の
    解析は check_ingest_freshness.py の `_parse_frontmatter` と同じく
    `yaml.safe_load` を使う（正規表現の手書きパースは値のクォート・エスケープの
    扱いが本番スクリプトと食い違うおそれがあるため避ける）。
    """
    new_sources = []
    for mgmt_path in changed_paths(cwd, ".wikicommit/source/**/*.md"):
        content = (cwd / mgmt_path).read_text(encoding="utf-8")
        m = _INGEST_FRONTMATTER_RE.match(content)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        source = fm.get("source")
        if not isinstance(source, dict) or source.get("type") != "path":
            continue
        source_path = source.get("path")
        if not source_path:
            continue
        if classify_source_status(cwd, source_path) == "new":
            new_sources.append(source_path)
    return new_sources


# Issue #350 — 3パターンの「次のステップ」案内文それ自体が SKILL.md 内の重複ハードコードから
# print_next_steps.py（スクリプト委譲パターン）に置き換わったため、案内文言のパース元も
# SKILL.md の静的テキストから、そのスクリプトの実際の出力に切り替える。これにより「ユーザーへ
# 実際に提示される git add コマンドと init.py の生成物が一致すること」という検証意図
# （Issue #86 と同種の配布漏れの検知）は変えずに保つ。
_VARIANT_ARGS = {
    "quartz_pages": ["--variant", "quartz_pages", "--quartz-status", "npm_install_completed_submodule_pending"],
    "quartz_only": ["--variant", "quartz_only", "--quartz-status", "npm_install_completed_submodule_pending"],
    "none": ["--variant", "none"],
}


def extract_git_add_paths(*, variant: str) -> list[str]:
    """print_next_steps.py が出力する「次のステップ」案内から git add 対象パスを抽出する。

    ハードコードした固定リストと突き合わせるのではなく、実際にユーザーへ提示される
    案内文言そのものをパースすることで、init.py の生成物と案内文が将来ズレた場合
    （Issue #86 と同種の配布漏れ）にこのテストが追従して検知できる。

    variant: "quartz_pages"（--quartz --quartz-pages）/ "quartz_only"（--quartz のみ）/
    "none"（--quartz なし）のいずれか。
    """
    result = subprocess.run(
        [sys.executable, str(PRINT_NEXT_STEPS_PY), *_VARIANT_ARGS[variant]],
        capture_output=True,
        text=True,
        check=True,
    )
    joined = result.stdout.replace("\\\n", " ")  # 行継続バックスラッシュを解消し1行に結合
    m = re.search(r"^\s*git add (.+)$", joined, re.MULTILINE)
    assert m, f"print_next_steps.py の出力に git add コマンドが見つかりません（variant={variant}）"
    return m.group(1).split()


def test_full_local_pipeline_commits_foundational_files_and_generated_pages(tmp_path):
    init_git_repo(tmp_path)

    # ── 1. install.sh（Skills 本体を .claude/skills/ に配置。ネットワーク不要） ──
    result = subprocess.run(
        ["bash", str(INSTALL_SH), "--yes"], cwd=tmp_path, capture_output=True, text=True, env=_GIT_ENV, check=False
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".claude" / "skills" / "wikicommit-init" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "wikicommit-generate" / "SKILL.md").is_file()

    # ── 2. /wikicommit-init（--quartz なし。ネットワーク・GitHub 到達性不要） ──
    result = subprocess.run(
        [sys.executable, str(INIT_PY)], cwd=tmp_path, capture_output=True, text=True, env=_GIT_ENV, check=False
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".wikicommit" / "config.yml").is_file()
    assert (tmp_path / ".wikicommit" / "schema").is_dir()
    assert (tmp_path / ".wikicommit" / "scripts").is_dir()

    # ── 3. SKILL.md の「次のステップ」案内どおりの初回コミット（Issue #86 の恒久対応） ──
    git(["add", *extract_git_add_paths(variant="none")], tmp_path, check=True)
    git(["commit", "-q", "-m", "chore: WikiCommit の基盤ファイルを追加"], tmp_path, check=True)

    # SKILL.md の案内どおりに git add した結果、init.py / install.sh が生成した
    # ファイルが一つ残らず追跡対象になっていること（配布漏れがあれば下記が失敗する）。
    assert git(["status", "--porcelain"], tmp_path, check=True).stdout == ""

    tracked = tracked_files(tmp_path)
    assert any(f.startswith(".claude/skills/") for f in tracked)
    assert ".wikicommit/config.yml" in tracked
    assert any(f.startswith(".wikicommit/schema/") for f in tracked)
    assert any(f.startswith(".wikicommit/scripts/") for f in tracked)

    # ── 4. /wikicommit-generate 相当（add_source.py 呼び出し） ──
    # ページ生成（パス2〜4）は LLM 呼び出しのためスコープ外。管理ファイルの登録のみ検証する。
    source_file = tmp_path / "raw" / "sample.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# Sample\n\nWikiCommit local smoke test source.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ADD_SOURCE_PY), "raw/sample.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    # The management file keeps the source's own extension and appends ".md"
    # (#573), so "raw/sample.md" registers as "raw/sample.md.md".
    mgmt_file = tmp_path / ".wikicommit" / "source" / "path" / "raw" / "sample.md.md"
    assert mgmt_file.is_file()
    assert "status: pending" in mgmt_file.read_text(encoding="utf-8")

    # LLM によるページ生成（パス2〜4）はスコープ外のため、生成結果をダミーページで代替する。
    wiki_page = tmp_path / ".wikicommit" / "entity" / "ja" / "DefinedTerm" / "sample.md"
    wiki_page.parent.mkdir(parents=True)
    wiki_page.write_text(
        """---
title: "サンプル用語"
lang: ja
type: "schema:DefinedTerm"
tags: []
sources:
  - type: path
    path: raw/sample.md
    hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
review_status: pending
generated_at: "2026-07-06"
generated_by: "claude-sonnet-5"
---

WikiCommit ローカルスモークテスト用のダミーページ。
""",
        encoding="utf-8",
    )
    mgmt_file.write_text(
        mgmt_file.read_text(encoding="utf-8").replace("status: pending", "status: generated", 1),
        encoding="utf-8",
    )

    # ── 5. /wikicommit-merge のコミット手順相当 ──
    # 品質チェック（validate_frontmatter.py 等）・ブランチ作成・PR 作成・auto-merge といった
    # GitHub API 呼び出しはスコープ外。「変更ファイルをコミット」の部分のみを検証する。
    # raw/sample.md（ingest 対象の実ソースファイル自体）は Issue #106 の対応により
    # wikicommit-merge のコミットに含める（<新規ソースファイル> 判定ロジック）。
    new_source_files = discover_new_source_files(tmp_path)
    assert new_source_files == ["raw/sample.md"]

    # SKILL.md ステップ 5（Issue #115）と同じく、<新規ソースファイル> には :(literal) を
    # 付与する。メタ文字を含むパスをプレフィックスなしで git add に渡すと無関係な
    # 別ファイルを誤って git add してしまう場合がある。
    git(
        ["add", "--", ".wikicommit/entity", ".wikicommit/source", *(f":(literal){p}" for p in new_source_files)],
        tmp_path,
        check=True,
    )
    git(["commit", "-q", "-m", "feat: add DefinedTerm/sample page"], tmp_path, check=True)

    tracked = tracked_files(tmp_path)
    assert ".wikicommit/entity/ja/DefinedTerm/sample.md" in tracked
    assert ".wikicommit/source/path/raw/sample.md.md" in tracked
    assert "raw/sample.md" in tracked

    # ── 6. 既に追跡済みの既存ファイルを ingest 登録した場合は対象外（Issue #106 対応方針の一部） ──
    # 「リポジトリに元々存在していた既存ファイル」と「Wiki 用に新規追加された生ソース」の
    # 区別は、明示的なフラグではなく git の追跡状態（untracked かどうか）で行う。
    existing_source = tmp_path / "existing" / "note.md"
    existing_source.parent.mkdir(parents=True)
    existing_source.write_text("既存プロジェクトのメモファイル。\n", encoding="utf-8")
    git(["add", "existing/note.md"], tmp_path, check=True)
    git(["commit", "-q", "-m", "chore: add pre-existing project file"], tmp_path, check=True)

    result = subprocess.run(
        [sys.executable, str(ADD_SOURCE_PY), "existing/note.md"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert discover_new_source_files(tmp_path) == []

    # ── 7. 削除された ソース管理ファイルはクラッシュせず対象外（SKILL.md ステップ 2 の 3.「削除は対象外」） ──
    # git status --porcelain は削除された管理ファイルも変更として報告するため、
    # 実体が存在しないファイルを frontmatter 解析しようとして FileNotFoundError に
    # ならないことを確認する。
    git(["rm", "-q", ".wikicommit/source/path/raw/sample.md.md"], tmp_path, check=True)
    assert discover_new_source_files(tmp_path) == []


def test_classify_source_status_detects_gitignored_source_file(tmp_path):
    """Issue #115 ケース 1: `.gitignore` で除外されたソースファイルは「追跡済み・
    変更なし」と出力上区別がつかず（どちらも空文字列）、`--ignored` なしでは
    「既にコミット済み」と誤判定されて警告なしに取りこぼされる。"""
    init_git_repo(tmp_path)
    (tmp_path / ".gitignore").write_text("raw/secret.pdf\n", encoding="utf-8")
    git(["add", ".gitignore"], tmp_path, check=True)
    git(["commit", "-q", "-m", "chore: add gitignore"], tmp_path, check=True)

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "secret.pdf").write_text("secret\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ADD_SOURCE_PY), "raw/secret.pdf"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert classify_source_status(tmp_path, "raw/secret.pdf") == "ignored"
    assert discover_new_source_files(tmp_path) == []


def test_discover_new_source_files_handles_non_ascii_path(tmp_path):
    """Issue #115 ケース 2: `core.quotePath` のデフォルト設定では、ソース管理
    ファイル自身のパスが非 ASCII 文字（日本語ファイル名等）を含む場合にダブル
    クォート + 8 進数エスケープされて出力される。un-quote しない実装は、
    そのエスケープ済み文字列をそのままパスとして読み込もうとして
    FileNotFoundError になる（`.wikicommit/source/` は ingest 対象のソースパスを
    ミラーするため、ソースが日本語ファイル名なら管理ファイルも同様になる）。"""
    init_git_repo(tmp_path)
    (tmp_path / "raw").mkdir()
    source_path = "raw/日本語文書.md"
    (tmp_path / source_path).write_text("非 ASCII パスのテスト\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ADD_SOURCE_PY), source_path],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    assert discover_new_source_files(tmp_path) == [source_path]


def test_classify_source_status_detects_source_deleted_after_registration(tmp_path):
    """Issue #368: `source.path` を ingest 登録した後にファイル自体が削除された
    場合、`git status --porcelain` は「追跡済み・変更なし」ケースと同じ空文字列を
    返すため、実在確認を git status より先に行わない実装は両者を区別できず、
    WARNING を出さないまま静かに `<新規ソースファイル>` から取りこぼす
    （Issue #115 が修正した3ケースと同種の失敗モード）。"""
    init_git_repo(tmp_path)
    (tmp_path / "raw").mkdir()
    source_path = "raw/paper-2024.pdf"
    (tmp_path / source_path).write_text("dummy source\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ADD_SOURCE_PY), source_path],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    # 登録直後はまだ untracked のため "new" と判定できることを確認しておく。
    assert classify_source_status(tmp_path, source_path) == "new"
    assert discover_new_source_files(tmp_path) == [source_path]

    # 登録後にソースファイル自体が削除されたケースを再現する。
    (tmp_path / source_path).unlink()

    assert classify_source_status(tmp_path, source_path) == "missing"
    assert discover_new_source_files(tmp_path) == []


def test_classify_source_status_glob_metachar_path_does_not_false_match(tmp_path):
    """Issue #115 ケース 3: `source.path` が glob メタ文字（`[`, `]` 等）を含む場合、
    `:(literal)` なしでは pathspec としてパターン解釈され、対象ファイルが存在しな
    くても同ディレクトリの無関係な未追跡ファイルに誤マッチしうる（`[2024]` が単一
    文字クラスとして解釈されるため）。"""
    init_git_repo(tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / ".gitkeep").write_text("", encoding="utf-8")
    git(["add", "raw/.gitkeep"], tmp_path, check=True)
    git(["commit", "-q", "-m", "chore: init raw dir"], tmp_path, check=True)

    mgmt_dir = tmp_path / ".wikicommit" / "source" / "path" / "raw"
    mgmt_dir.mkdir(parents=True)
    (mgmt_dir / "report[2024].md").write_text(
        """---
source:
  type: path
  path: "raw/report[2024].pdf"
  hash: sha256:0000000000000000000000000000000000000000000000000000000000000000

schema:
status: pending
last_generated_at:
generated_pages: []
failed_pages: []
---
""",
        encoding="utf-8",
    )
    # raw/report[2024].pdf 自体は存在しない（登録後に削除された、等を想定）。
    # 同ディレクトリに無関係な未追跡ファイルが存在する状態を作る。
    (tmp_path / "raw" / "report2.pdf").write_text("decoy\n", encoding="utf-8")

    assert classify_source_status(tmp_path, "raw/report[2024].pdf") == "missing"
    assert discover_new_source_files(tmp_path) == []
    # decoy 自体は :(literal) の影響を受けず正しく "new" と判定できることも確認する。
    assert classify_source_status(tmp_path, "raw/report2.pdf") == "new"


# init.py が自動取得しない（SKILL.md 記載どおりユーザーが `git submodule add` で
# 手動追加する）パス。--quartz の git add リストに含まれるが init.py の生成物としては
# 存在しないため、下記の存在確認からは除外する。
_QUARTZ_MANUAL_SUBMODULE_PATHS = {".gitmodules", "quartz"}


def _assert_git_add_guidance_covers_every_generated_file(repo: Path, paths: list[str]) -> None:
    """案内リストどおりに git add / commit した後、未追跡ファイルが 1 つも残らないことを検証する。

    下の 2 テストが元々持っていた「案内リストの各パスが実在すること」という検証は
    **案内リスト → 生成物**の一方向でしかなく、「生成されているのに案内に書かれていない」
    という向きの漏れを構造的に検知できなかった。実際 Issue #434 で追加された
    install-local-plugins.cjs が案内から漏れたまま気づかれず、`--quartz --quartz-pages`
    で init した全リポジトリで初回 push の GitHub Pages ビルドが postinstall の
    MODULE_NOT_FOUND で必ず失敗していた（Issue #556。decameron-wiki / saitama-city-wiki の
    2 例で再現）。非 --quartz 経路にだけ存在した `git status --porcelain == ""` の逆向き
    検証を --quartz 経路にも移植する。
    """
    # .gitmodules / quartz は init.py の生成物ではなくユーザーが `git submodule add` で
    # 手動追加する想定のため（_QUARTZ_MANUAL_SUBMODULE_PATHS）、この時点では存在せず
    # git add に渡すと pathspec エラーでコマンド全体が落ちる。除いて add する。
    addable = [rel_path for rel_path in paths if rel_path not in _QUARTZ_MANUAL_SUBMODULE_PATHS]
    git(["add", *addable], repo, check=True)
    git(["commit", "-q", "-m", "chore: add WikiCommit foundational files"], repo, check=True)
    leftover = _git_status_porcelain(repo, [])
    assert leftover == "", (
        "案内どおりに git add した後も未追跡ファイルが残っています"
        f"（案内リストへの追加漏れ）:\n{leftover}"
    )


def test_quartz_only_git_add_paths_match_generated_files(tmp_path):
    """--quartz 単体（--quartz-pages なし）選択時の SKILL.md 案内が init.py --quartz の
    実際の生成物と一致することを検証する。

    非 --quartz 経路は上のテストで検証済みだが、--quartz 経路の git add リスト
    （quartz.config.yaml・package.json・quartz-plugins 等）は
    これまでどのテストからも実行されておらず、Issue #86 と同種の配布漏れが
    --quartz 選択時にだけ発生しても検知できなかった。--quartz-pages を渡していない
    ため deploy.yml は生成されず、SKILL.md の quartz_only 案内にも含まれない（Issue #335）。
    """
    init_git_repo(tmp_path)
    subprocess.run(
        ["bash", str(INSTALL_SH), "--yes"], cwd=tmp_path, capture_output=True, text=True, env=_GIT_ENV, check=True
    )
    result = subprocess.run(
        [sys.executable, str(INIT_PY), "--quartz"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    paths = extract_git_add_paths(variant="quartz_only")
    assert "quartz-plugins" in paths  # マーカー境界が正しく他の変種の行を拾っていないことの確認
    assert ".github/workflows/deploy.yml" not in paths
    for rel_path in paths:
        if rel_path in _QUARTZ_MANUAL_SUBMODULE_PATHS:
            continue
        assert (tmp_path / rel_path).exists(), f"{rel_path} が init.py --quartz で生成されていません"

    _assert_git_add_guidance_covers_every_generated_file(tmp_path, paths)


def test_quartz_pages_git_add_paths_match_generated_files(tmp_path):
    """--quartz --quartz-pages 選択時の SKILL.md 案内が init.py の実際の生成物（deploy.yml を
    含む）と一致することを検証する（Issue #335）。"""
    init_git_repo(tmp_path)
    subprocess.run(
        ["bash", str(INSTALL_SH), "--yes"], cwd=tmp_path, capture_output=True, text=True, env=_GIT_ENV, check=True
    )
    result = subprocess.run(
        [sys.executable, str(INIT_PY), "--quartz", "--quartz-pages"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    paths = extract_git_add_paths(variant="quartz_pages")
    assert "quartz-plugins" in paths
    assert ".github/workflows/deploy.yml" in paths
    for rel_path in paths:
        if rel_path in _QUARTZ_MANUAL_SUBMODULE_PATHS:
            continue
        assert (tmp_path / rel_path).exists(), (
            f"{rel_path} が init.py --quartz --quartz-pages で生成されていません"
        )

    _assert_git_add_guidance_covers_every_generated_file(tmp_path, paths)
