"""`wikicommit-explorer` が持つ 2 つの `sortTier` の同期を検証する (Issue #946)。

並び順のロジックは同じプラグインの中に**写しが 2 つ**ある。`WikiCommitExplorer.tsx` の
`explorerSortFn` が正で、`wikicommit-explorer.inline.ts` の `defaultSortFn` は
そちらが復元できなかったときのフォールバックである（コンポーネントが `.toString()` で
`data-data-fns` 属性へ載せた本体を、ブラウザが `new Function(...)` として復元し、
`buildFileTrie()` の中で `defaultSortFn` を上書きする）。

**フォールバックが効くのは「一瞬」ではない。** 木は `buildFileTrie()` の解決後に一度だけ
描画されるので、`defaultSortFn` で描いてから描き直す経路は無い。`data-data-fns` が無い・
`JSON.parse` が落ちる（`catch` はログを出すだけ）といった場合に `defaultSortFn` が
そのページの並び順を**最後まで**決める。したがって片方だけ直したときの症状は、
その経路に落ちた読者が**ずっと古い並び順を見る**ことであり、通常の経路では
**何も起きない**（だから目視では見つからない）。

後者のコメントは以前から「must still match so that fallback path doesn't regress to an
older ordering」と書いていたが、**それを強制するものが無かった**。Issue #228 の
`tests/test_quartz_plugins_lang_segment_sync.py` は `^const LANG_SEGMENT_RE = (/.+/)$` を
行頭アンカーで探すため、関数本体の中にインデントされて置かれたこの 2 つの写しは
どちらも射程に入っていない。

`test_template_mirror_sync.py`・Issue #228 と同じ「内容一致を CI で強制する」パターンを
採る。ただし 2 つは同じ言語ではない（TypeScript と、型注釈もセミコロンも異なる素の
JavaScript）ため、逐語比較ではなく**正規化してから**比較する — 型注釈・コメント・
セミコロン・空白を落とすと、残るのは分岐の条件と tier の値そのものになる。

**照合の対象は `sortTier` の本体だけである。** 2 つの比較関数の残り（tier が同値のときの
`displayName` の突き合わせとフォルダ/ファイルの前後）は比較しない — そこは
`(a.displayName || "")` と `a.displayName` で既に食い違っており、全体を突き合わせる形には
そもそもできない。したがってこのテストが守るのは tier のロジックに限られ、tie-break の
drift は引き続きどのテストも見ていない。
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
EXPLORER_DIR = (
    REPO_ROOT
    / ".claude"
    / "skills"
    / "wikicommit-init"
    / "scripts"
    / "templates"
    / "quartz-plugins"
    / "wikicommit-explorer"
)

# (人が読む名前, ソースファイル) の一覧。Issue #946 の対象ファイル。
SORT_TIER_SOURCES = [
    (
        "WikiCommitExplorer.tsx (explorerSortFn)",
        EXPLORER_DIR / "src" / "components" / "WikiCommitExplorer.tsx",
    ),
    (
        "wikicommit-explorer.inline.ts (defaultSortFn)",
        EXPLORER_DIR / "src" / "components" / "scripts" / "wikicommit-explorer.inline.ts",
    ),
]

LINE_COMMENT = re.compile(r"//.*")
# `(n: FileTrieNode): number` と `(n)` を同じ形に落とすための型注釈除去。
#
# **引数・返り値の位置に限る**（`)` か `=>` が続く形だけを見る）。素朴に `: 識別子` を
# 全部落とすと、オブジェクトリテラルの値やテルナリの右辺まで消える — 一方が
# `{root: true}`、他方が `{root: false}` を返しても双方 `{root}` に潰れて一致し、
# **本物の drift が緑のまま通る**。この正規化が避けるべきなのはまさにその状態であり、
# 落とし過ぎより落とさな過ぎ（偽陽性で赤くなる）側へ倒す。
# なお現在の抽出は本体の `{` から始まるためシグネチャを含まず、この置換は実際には
# 何にも当たらない — 将来 sortTier の中に型注釈付きのヘルパーが現れた場合の保険である。
TYPE_ANNOTATION = re.compile(r":\s*[A-Za-z_][A-Za-z0-9_]*(?=\s*(?:\)|=>))")


def _extract_sort_tier_body(path: Path) -> str:
    """`sortTier` のアロー関数本体を、波括弧の対応を数えて切り出す。

    正規表現で終端を探さないのは、本体の中に `if (...) { ... }` が複数あり、最初の `}` が
    関数の終わりではないため。開始位置だけを文字列検索で決めて、そこから数える。

    返す本体は行コメントを落とした後のものである（下記の理由により、数える前に落とす）。
    """
    # 波括弧を数える前にコメントを落とす。コメントの中の `{` / `}` はコードの対応に
    # 参加しないため、生のまま数えると本体の終端が静かにずれる（コードの断片を引用した
    # 1 行が対応しない `}` を含めば走査が早く終わり、`{` を含めば sortTier の閉じ括弧を
    # 通り過ぎて外のコードが混ざる）。
    text = LINE_COMMENT.sub("", path.read_text(encoding="utf-8"))
    start = text.find("const sortTier =")
    assert start != -1, (
        f"{path} に `const sortTier =` が見つかりません。"
        " ファイルが移動・リネームされた場合は tests/test_explorer_sort_tier_sync.py の"
        " SORT_TIER_SOURCES も更新してください。"
    )

    open_brace = text.find("{", start)
    assert open_brace != -1, f"{path} の sortTier に本体の `{{` が見つかりません"

    depth = 0
    for index in range(open_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[open_brace + 1 : index]
    raise AssertionError(f"{path} の sortTier の `{{` が閉じられていません")


def _normalize(body: str) -> str:
    """2 つの言語の書き方の違いだけを落とし、分岐の条件と tier の値を残す。"""
    body = LINE_COMMENT.sub("", body)
    body = TYPE_ANNOTATION.sub("", body)
    body = body.replace(";", "")
    return "".join(body.split())


def test_sort_tier_sources_exist():
    for name, path in SORT_TIER_SOURCES:
        assert path.is_file(), f"{name}: ソースファイルが見つかりません: {path}"


def test_sort_tier_logic_is_identical_across_the_two_copies():
    bodies = {name: _normalize(_extract_sort_tier_body(path)) for name, path in SORT_TIER_SOURCES}

    distinct = set(bodies.values())
    assert len(distinct) == 1, (
        "explorer の sortTier が 2 つの写しの間で一致していません"
        "（drift 検知。Issue #946）。片方だけ直すと、data-data-fns を復元できなかった"
        f"読者にだけ古い並び順が最後まで出ます: {bodies}"
    )


def test_the_normalization_still_distinguishes_a_changed_tier_value():
    """正規化が緩すぎないことを確かめる。空白とセミコロンを落とす処理は、**値の違いまで**
    落としてしまうと、この同期テスト自体が何も検出しなくなる — その状態は緑のまま通る。"""
    _, tsx_path = SORT_TIER_SOURCES[0]
    body = _extract_sort_tier_body(tsx_path)

    assert _normalize(body) != _normalize(body.replace("return -2", "return -9", 1))


def test_the_normalization_keeps_a_value_that_follows_a_colon():
    """型注釈の除去が、コロンに続く**値**まで巻き込まないことを確かめる。

    巻き込むと `{root: true}` と `{root: false}` が双方 `{root}` に潰れ、本物の drift が
    緑のまま通る — 上のテストは tier の値しか動かさないため、この形を検出できない。
    """
    assert _normalize("return {root: true}") != _normalize("return {root: false}")
    assert _normalize("return n.isFolder ? tierA : tierB") != _normalize(
        "return n.isFolder ? tierA : tierC"
    )


def _fake_sort_tier_source(comment: str) -> str:
    return (
        "const explorerSortFn = (a, b) => {\n"
        "  const sortTier = (n) => {\n"
        f"{comment}"
        "    if (n.isFolder) {\n"
        "      return -2\n"
        "    }\n"
        "    return 0\n"
        "  }\n"
        "  return sortTier(a) - sortTier(b)\n"
        "}\n"
    )


def test_an_unbalanced_brace_in_a_comment_does_not_move_the_body_boundary(tmp_path):
    """コメント内の対応しない `{` / `}` で本体の終端がずれないことを確かめる。

    生のまま数えると、コードの断片を引用した 1 行（`… closes with }` / `… opens with {`）が
    入るだけで終端が動く — 前者は走査が早く終わって本体が途中で切れ、後者は sortTier の
    閉じ括弧を通り過ぎて外のコードが混ざる。2 つの写しはコメントが異なるので、
    tier のロジックとは無関係な差で CI が赤くなる。
    """
    for name, comment in [
        ("closing", "    // the language branch above closes with }\n"),
        ("opening", "    // the folder branch below opens with {\n"),
    ]:
        source = tmp_path / f"fake-{name}.ts"
        source.write_text(_fake_sort_tier_source(comment), encoding="utf-8")

        body = _extract_sort_tier_body(source)

        assert "return 0" in body, f"{name}: 本体が sortTier の末尾まで届いていません"
        assert "sortTier(a)" not in body, f"{name}: 本体が sortTier の外まで伸びています"


def test_the_extracted_body_covers_exactly_sort_tier_in_both_copies():
    """実ファイル側でも、抽出範囲が sortTier の本体ちょうどであることを固定する。"""
    for _, path in SORT_TIER_SOURCES:
        body = _extract_sort_tier_body(path)

        assert "//" not in body, f"{path}: 抽出結果に行コメントが残っています"
        assert body.count("{") == body.count("}"), f"{path}: 抽出した本体の波括弧が不均衡です"
        assert "return 0" in body, f"{path}: 抽出した本体が sortTier の末尾まで届いていません"
        assert "aTier" not in body, f"{path}: 抽出した本体が sortTier の外まで伸びています"
