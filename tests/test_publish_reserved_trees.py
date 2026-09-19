"""publish 層が root 直下に予約するページツリーが、両プラグインに登録されているか (Issue #957)。

`convert_wikilinks.py` が `content/` 直下に作るビルド生成ツリーは、エンティティのパス文法
（`<lang>/<Type>/<slug>`）に当たらない。したがって**両方の publish プラグインが名前で知って
いる必要がある** — `wikicommit-graph` は `overview/` を言語ファセットに出さないため、
`wikicommit-explorer` は両者を Type フォルダに埋もれさせないためである。

**Issue #585 は `content/overview/` を作ったときに、どちらにも登録しなかった。** 症状は
両方とも静かなものだった: グラフのコントロールバーに `overview` という存在しない言語が
並び（しかも読者が実在の言語を選ぶと俯瞰ページ自体が消える）、explorer では Type フォルダに
紛れる。Issue #946 が explorer 側を、Issue #957 が graph 側を直した — **同じ登録漏れが
2 回続いた**ため、3 回目を CI で止める。

`tests/test_explorer_sort_tier_sync.py`・Issue #228 と同じ「内容一致を CI で強制する」形で、
正本は `convert_wikilinks.py` の `RESERVED_PUBLISH_TREES` である。

## このテストの限界

**grep 相当であり、登録の正しさは検証しない。** 名前がコメントの中に現れるだけでも通る。
捕まえたいのは「新しいツリーを作ってプラグインに登録し忘れる」という Issue #585 の失敗
そのものであって、分類が意味的に正しいかではない（そちらは各プラグインの単体テストが見る）。

**`src/` しか見ないので、`dist/` が古いままであることは捕まえない。** 利用者のリポジトリへ
実際に届くのは `dist/` の方であり（`quartz-plugins/` は `update: overwrite`）、再生成を
落とすとこのテストも各プラグインの単体テストも緑のまま利用者には旧挙動が届く。それは
Issue #957 の完了条件 3 が人手で担保する範囲である。
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS = REPO_ROOT / ".wikicommit" / "scripts"
PLUGINS = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "quartz-plugins"
)

# 各ツリー名が現れていなければならないソース。graph は分類（`classifyNode`）、explorer は
# 並び順（`sortTier`）で使う。explorer が 2 本あるのは同じロジックの写しが 2 つあるため
# （Issue #946。`tests/test_explorer_sort_tier_sync.py` がその 2 本の同期を別途見ている）。
PLUGIN_SOURCES = (
    PLUGINS / "wikicommit-graph" / "src" / "util" / "nodeFilter.ts",
    PLUGINS / "wikicommit-explorer" / "src" / "components" / "WikiCommitExplorer.tsx",
    PLUGINS / "wikicommit-explorer" / "src" / "components" / "scripts" / "wikicommit-explorer.inline.ts",
)


def _load_convert_wikilinks():
    """`convert_wikilinks.py` をモジュールとして読む（既存テストと同じパターン）。

    兄弟モジュールを名前で import するため、スクリプト自身のディレクトリを先に
    `sys.path` へ置く必要がある。
    """
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "convert_wikilinks", SCRIPTS / "convert_wikilinks.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS))
    return module


_convert_wikilinks = _load_convert_wikilinks()
RESERVED = _convert_wikilinks.RESERVED_PUBLISH_TREES


def test_the_list_is_not_empty_and_holds_plain_names():
    assert RESERVED, "空だと下の assert がすべて vacuously true になる"
    for name in RESERVED:
        assert isinstance(name, str) and name, name
        assert "/" not in name, f"{name}: root 直下の 1 セグメントであること"


def test_the_names_the_script_actually_writes_are_the_ones_listed():
    """定数が実装から離れていないこと — 両方が実際の書き出しに使われている。"""
    assert _convert_wikilinks.SOURCES_DIR_NAME in RESERVED
    assert _convert_wikilinks.OVERVIEW_DIR_NAME in RESERVED


def test_every_reserved_tree_is_registered_in_every_publish_plugin():
    """Issue #585 の失敗（作ったがどちらにも登録しない）を 3 回目の前に止める。"""
    missing: list[str] = []
    for source in PLUGIN_SOURCES:
        assert source.is_file(), f"{source} が無い（パスが動いたならこのテストを直す）"
        text = source.read_text(encoding="utf-8")
        for name in RESERVED:
            if f'"{name}"' not in text:
                missing.append(f"{source.relative_to(REPO_ROOT)}: {name!r}")
    assert not missing, (
        "publish 層の予約ツリーが登録されていない箇所がある。"
        "graph は classifyNode() に、explorer は sortTier() に足すこと:\n  "
        + "\n  ".join(missing)
    )


def test_tags_and_assets_are_deliberately_absent():
    """対象外を明記する — 書かないと、次に読む人には登録漏れに見える。

    `tags/` は Quartz が書くツリーであり `convert_wikilinks.py` の所管ではない
    （explorer 側も `sortTier` ではなく `filterFn` で落としている）。`assets/` は
    非 `.md` のみでページを持たないため、どちらのプラグインにもノード・フォルダとして
    現れない。
    """
    assert "tags" not in RESERVED
    assert "assets" not in RESERVED
