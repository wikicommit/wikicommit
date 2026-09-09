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

Issue #801 で `CHANGELOG.md` は「最新の 1 版 + 過去版の索引」になり、確定した過去の版は
`changelog/<version>.md` へ移った。**この同期は対を列挙して持たず走査で行う** — 版を
1 つ足すたびにファイルが 1 つ増えるため、リストで持つとリリースのたびに更新箇所が
1 つ増え、更新漏れがそのまま「そのファイルだけ Skill ツリー側が古い」として残る
（このテストが防ごうとしている状態そのものである）。構造そのもの（索引と実ファイルの
一致・確定版が高々 1 つ）は `tests/test_changelog_structure.py` が見る。
"""

from pathlib import Path

from _publication import skip_unless_development_repository

REPO_ROOT = Path(__file__).parent.parent
ROOT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"
JA_CHANGELOG = REPO_ROOT / "CHANGELOG_ja.md"
SKILL_CHANGELOG = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "CHANGELOG.md"
ROOT_ARCHIVE = REPO_ROOT / "changelog"
SKILL_ARCHIVE = SKILL_CHANGELOG.parent / "changelog"


def _archive_names(directory: Path) -> set[str]:
    return {p.name for p in directory.glob("*.md")} if directory.is_dir() else set()


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


def test_the_header_names_all_five_places_to_update():
    """版を上げるときの更新箇所は 3 つ → 4 つ → 5 つと増えてきた。数だけ直して項目を
    足し忘れると、Skill ツリー側のコピーが黙って古いまま残る（4 つ目）か、回転が
    起こらず CHANGELOG.md が全履歴を抱えたままになる（5 つ目。Issue #801）。"""
    text = ROOT_CHANGELOG.read_text(encoding="utf-8")
    assert "update all five of these together" in text
    assert ".claude/skills/wikicommit-init/CHANGELOG.md" in text
    assert "changelog/<version>.md" in text


def test_the_archive_exists_in_both_places():
    """`install.sh` も `npx skills add` も Skill ディレクトリ配下しか運ばないので、
    ルートにしか無い過去版は利用者に一度も届かない — 索引だけが届いて、その行が指す先が
    存在しない状態になる。"""
    assert ROOT_ARCHIVE.is_dir(), ROOT_ARCHIVE
    assert SKILL_ARCHIVE.is_dir(), SKILL_ARCHIVE


def test_every_archived_version_is_identical_in_both_places():
    """対を列挙せず走査する。版が増えるたびに対が 1 つ増えるため、リストで持つと
    リリースのたびに更新箇所が増え、漏れがそのまま「そのファイルだけ古い」として残る。"""
    root_names, skill_names = _archive_names(ROOT_ARCHIVE), _archive_names(SKILL_ARCHIVE)
    assert root_names == skill_names, (
        "changelog/ の中身がルートと Skill ツリーで食い違っています: "
        f"ルートのみ={sorted(root_names - skill_names)}, "
        f"Skill ツリーのみ={sorted(skill_names - root_names)}"
    )
    assert root_names, "changelog/ が空です（過去版が 1 つも無い）"
    for name in sorted(root_names):
        assert (ROOT_ARCHIVE / name).read_text(encoding="utf-8") == \
            (SKILL_ARCHIVE / name).read_text(encoding="utf-8"), f"changelog/{name} が食い違っています"


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

    offenders = []
    # 過去版も同じ検査を掛ける（Issue #801）。既存エントリは英語なので回帰防止として
    # 働く一方、外すと分割した瞬間に 1392 行中 1147 行がこの検査の外へ出る。
    for path in [ROOT_CHANGELOG, *sorted(ROOT_ARCHIVE.glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        # ヘッダー（最初の見出しまで）＋各トップレベル項目を、それぞれ 1 つの塊として見る。
        for block in re.split(r"\n(?=- )", text):
            lines = [line for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            japanese = [line for line in lines if cjk.search(line)]
            if len(japanese) > len(lines) * 0.5:
                offenders.append((path.name, lines[0][:80], len(japanese), len(lines)))

    assert not offenders, (
        "CHANGELOG に日本語で書かれた箇所があります。正本は英語です "
        "（日本語版は CHANGELOG_ja.md）: "
        + "; ".join(f"{name}: {head!r} ({jp}/{total} 行)" for name, head, jp, total in offenders)
    )
