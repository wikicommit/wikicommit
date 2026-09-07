"""CHANGELOG.md がルートと Skill ツリーで一致していることを検証する (Issue #713)。

同じ内容を 2 箇所に置く理由は、届く範囲が違うことにある:

- リポジトリのルート — 編集する側。開発リポジトリと、`git archive` が作る
  配布リポジトリのルートに置かれる
- `.claude/skills/wikicommit-init/CHANGELOG.md` — そのコピー。`install.sh` も
  `npx skills add` も **Skill ディレクトリ配下しか運ばない**（前者は `SKILLS`
  配列の各ディレクトリに `find -type f` を回すだけ）ため、ここに置かない限り
  このファイルは利用者の wiki リポジトリに一度も届かない

Issue #577 はこのファイルを「利用者が前回インストールした版から何が変わったかを
知る唯一の手段」と位置づけているが、その唯一の手段が update を実行する場所から
読めていなかった。`/wikicommit-update` は Skill ツリー側を読む。

`tests/test_version_sync.py`（`_version.py` と `plugin.json` の版の一致）と同じ
「生成スクリプト化ではなく内容一致を CI で強制する」軽量パターンを採る。

`CHANGELOG_ja.md`（ルートのみ）はこの同期の対象外である (Issue #772)。正本は英語の
`CHANGELOG.md` で、日本語版は `README_ja.md` と同じ「読みやすさのための便宜」に留まり、
機械が読む対象ではないためドリフトを許容する — 同期を強制すると、配布されず誰も
機械的に読まないファイルのために全エントリの逐語訳が必須になる。
"""

from pathlib import Path

from _publication import skip_unless_development_repository

REPO_ROOT = Path(__file__).parent.parent
ROOT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
JA_CHANGELOG = REPO_ROOT / "CHANGELOG_ja.md"
SKILL_CHANGELOG = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "CHANGELOG.md"


def test_both_copies_exist():
    assert ROOT_CHANGELOG.is_file()
    assert SKILL_CHANGELOG.is_file(), (
        "Skill ツリー側の CHANGELOG.md がありません。ここに無いと install.sh も "
        "npx skills add もこのファイルを運ばず、/wikicommit-update が読む先が存在しません"
    )


def test_the_two_copies_are_identical():
    root = ROOT_CHANGELOG.read_text(encoding="utf-8")
    skill = SKILL_CHANGELOG.read_text(encoding="utf-8")
    assert root == skill, (
        "CHANGELOG.md がルートと .claude/skills/wikicommit-init/ で食い違っています。"
        "版を上げるときは両方を更新してください（ルートが編集する側で、Skill ツリー側はそのコピー）"
    )


def test_the_header_names_all_four_places_to_update():
    """版を上げるときの更新箇所は 3 つから 4 つになった。数だけ直して項目を足し忘れると、
    Skill ツリー側のコピーが黙って古いまま残る。"""
    text = ROOT_CHANGELOG.read_text(encoding="utf-8")
    assert "update all four of these together" in text
    assert ".claude/skills/wikicommit-init/CHANGELOG.md" in text


def test_the_header_forbids_development_repository_paths():
    """このファイルは利用者の wiki リポジトリまで運ばれるが、そこから docs/ は辿れない。
    tools/check_distributed_path_refs.py が実際に止めるので、規約は書くだけでなく
    書いてあることを確かめておく（規約が消えると次に書く人が理由を知らないまま踏む）。"""
    text = ROOT_CHANGELOG.read_text(encoding="utf-8")
    assert "Do not write `docs/`, `Issues/`, or `dev/` paths in this file." in text


def test_the_japanese_edition_exists_and_states_it_is_not_canonical():
    """日本語版はドリフトを許容する（同期テストを掛けない）が、そのことを読む人が
    知らなければ、古い内容を正本と取り違える。位置づけの明示だけは強制する (Issue #772)。

    `CHANGELOG_ja.md` は正本でも配布物でもないため公開スナップショットには出さない
    （dev/publication-scope.md §3）。下の test_the_japanese_edition_is_not_distributed
    とは向きが逆で、あちらは「Skill ツリーに置かれていないこと」を公開側でも確かめられる
    （Issue #788）。"""
    skip_unless_development_repository("CHANGELOG_ja.md")
    assert JA_CHANGELOG.is_file()
    text = JA_CHANGELOG.read_text(encoding="utf-8")
    assert "`CHANGELOG.md`（英語）の日本語版です" in text
    assert "正本は英語版" in text


def test_the_japanese_edition_is_not_distributed():
    """install.sh も npx skills add も Skill ディレクトリ配下しか運ばない。日本語版を
    そこへ置くとファイルが 4 つになり、ドリフトを許容したファイルが利用者へ届く
    （/wikicommit-update が読むのは英語版である） (Issue #772)。"""
    assert not (SKILL_CHANGELOG.parent / "CHANGELOG_ja.md").exists()


def test_the_canonical_changelog_is_written_in_english():
    """配布物の中で CHANGELOG だけが日本語という状態に戻さない (Issue #772)。
    日本語のリテラル（メッセージ本文・タグ・ページタイトルの例）は引用として現れうるため、
    「日本語の散文が本文の大半を占めていないこと」を粗く見る。

    判定はファイル全体ではなく**エントリ単位**で行う。このファイルは追記のみで伸びるため、
    全体に対する割合で見ると許容量が版を追うごとに増え、最も起こりやすい退行 —
    新しいエントリ 1 件だけが日本語で書かれる — を素通りさせる（1200 行時点で
    5% の許容量は 60 行あり、このファイルのエントリ 1 件は 10〜25 行に収まる）。
    エントリ単位なら、日本語で書かれたエントリはその中でほぼ全行が該当するのに対し、
    引用リテラルを含む英語のエントリは数行に留まるため、両者が分離する（実測の最大は
    7 行中 2 行 = 0.29）。"""
    import re

    cjk = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
    text = ROOT_CHANGELOG.read_text(encoding="utf-8")

    # ヘッダー（最初の見出しまで）＋各トップレベル項目を、それぞれ 1 つの塊として見る。
    blocks = re.split(r"\n(?=- )", text)
    offenders = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        japanese = [line for line in lines if cjk.search(line)]
        if len(japanese) > len(lines) * 0.5:
            offenders.append((lines[0][:80], len(japanese), len(lines)))

    assert not offenders, (
        "CHANGELOG.md に日本語で書かれた箇所があります。正本は英語です "
        "（日本語版は CHANGELOG_ja.md）: "
        + "; ".join(f"{head!r} ({jp}/{total} 行)" for head, jp, total in offenders)
    )
