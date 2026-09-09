"""WikiCommit 自身のバージョンが 2 箇所で一致していることを検証する (Issue #577)。

版の source of truth は 2 つあり、届く範囲が異なるため一本化できない:

- `.claude/skills/wikicommit-init/scripts/templates/scripts/_version.py`
  — `init.py` が `.wikicommit/scripts/_version.py` として展開するため、
    インストール先の wiki リポジトリまで届く唯一の情報源。`config.yml` の
    `wikicommit_version`・ページの `generated_with` / `translated_with` は
    すべてここから読む
- `.claude-plugin/plugin.json` の `version`
  — Claude Code の plugin 機構（`claude plugin list` / `/plugin update`・
    マーケットプレイス掲載）が読む。配布リポジトリのルートに置かれ、
    インストール先には届かない

同じ番号を 2 箇所に書くことになるため、`tests/test_skill_distribution_list_sync.py`
（install.sh と plugin.json の配布リスト同期）と同じ「生成スクリプト化ではなく
内容一致を CI で強制する」軽量パターンを採る。片方だけ bump した状態では
このテストが失敗する。

`pyproject.toml` の `version` はこの同期の対象外 — あちらは開発リポジトリ自身の
Python パッケージ宣言（テスト・lint 依存用）である。揃え続ける理由が無いのは、
`packages = []` で配布パッケージではなく、`version` の消費者がリポジトリに 1 つも
無く、版を上げる契機（型テンプレート・生成ルールの変更）とテスト・lint の依存宣言が
無関係だからである。**実際に乖離している**が、それが想定どおりの結果であって直す
べきドリフトではない（`_version.py` の docstring 参照）。
"""

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VERSION_PY = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts"
    / "templates" / "scripts" / "_version.py"
)
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
CONFIG_TEMPLATE = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts"
    / "templates" / "config.yml"
)

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def _version_py_version() -> str:
    spec = importlib.util.spec_from_file_location("_wikicommit_version_test", VERSION_PY)
    assert spec is not None and spec.loader is not None, f"{VERSION_PY} を読み込めません"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.VERSION


def _plugin_json_version() -> str:
    manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    assert "version" in manifest, (
        f"{PLUGIN_JSON} に version フィールドがありません（Issue #577 で付与を決定済み。"
        " claude plugin validate が未指定を warning にするため掲載時に必要）"
    )
    return manifest["version"]


def test_version_py_is_semver():
    version = _version_py_version()
    assert SEMVER_RE.match(version), (
        f"{VERSION_PY} の VERSION が semver ではありません: {version!r}"
    )


def test_plugin_json_version_is_semver():
    version = _plugin_json_version()
    assert SEMVER_RE.match(version), (
        f"{PLUGIN_JSON} の version が semver ではありません: {version!r}"
    )


def test_version_py_and_plugin_json_agree():
    version_py = _version_py_version()
    plugin_json = _plugin_json_version()

    assert version_py == plugin_json, (
        "WikiCommit の版が 2 箇所で食い違っています（drift 検知。Issue #577）。"
        f" _version.py: {version_py!r} / plugin.json: {plugin_json!r}。"
        " 版を上げるときは両方と CHANGELOG.md をまとめて更新してください。"
    )


def test_config_template_has_version_placeholder():
    """init.py が {VERSION} を置換して wikicommit_version を刻印する
    （置換対象が消えると刻印が黙って行われなくなる）。"""
    text = CONFIG_TEMPLATE.read_text(encoding="utf-8")
    assert "wikicommit_version: \"{VERSION}\"" in text, (
        f"{CONFIG_TEMPLATE} に wikicommit_version: \"{{VERSION}}\" がありません"
    )


def test_changelog_exists_and_lists_current_version():
    """配布リポジトリの git log は単一の同期コミットしか持たないため、
    CHANGELOG.md が利用者への唯一の変更伝達手段になる（Issue #577）。"""
    changelog = REPO_ROOT / "CHANGELOG.md"
    assert changelog.exists(), f"{changelog} が存在しません"
    text = changelog.read_text(encoding="utf-8")
    version = _version_py_version()
    assert f"[{version}]" in text or f"## {version}" in text, (
        f"CHANGELOG.md に現在の版 {version} のエントリがありません"
    )
