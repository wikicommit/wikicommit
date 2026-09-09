"""`CHANGELOG.md` の回転が実際に行われていることを検証する (Issue #801)。

このファイルは「利用者が前回インストールした版から何が変わったかを知る唯一の手段」
であり (Issue #577)、`/wikicommit-update` Step 9 が Skill ツリー側を読む。ところが
全履歴が 1 ファイルにあると、**読み込み量が版の差に比例しない** — 1 版遅れの利用者も
10 版遅れの利用者も同じ 104KB（約 30K トークン）を読むことになり、14KB の SKILL.md が
104KB のファイルを読むという逆転が実際に起きていた。

Issue #801 の答えは 1 リリース 1 ファイル + 索引（Django・Node.js が採る形）で、
新しい形式もツールも要らない代わりに**リリースのたびに回転が要る**。回転は忘れられる
種類の手順なので、忘れたことがここで落ちる。

不変条件は 3 つで、`CHANGELOG.md` 冒頭の bump 手順 5 番目に対応する:

1. `CHANGELOG.md` が持つ確定版（`## [x.y.z] - <date>`）は高々 1 つ
2. 索引の各行に対応する `changelog/<version>.md` が実在する
3. `changelog/*.md` の各ファイルが索引に載っている

2 と 3 は双方向であり、片方だけだと片側の追加が黙って通る — 索引だけ足せば行き先の
無いリンクが、ファイルだけ足せば誰にも辿れない版が残る。

ルートと Skill ツリーの一致は `tests/test_changelog_sync.py` の担当で、ここは
**構造**だけを見る。両方をルートに対して掛けるのは、ルートが編集する側であり
Skill ツリー側はそのコピーだからである。
"""

import re

from _publication import REPO_ROOT

CHANGELOG = REPO_ROOT / "CHANGELOG.md"
ARCHIVE = REPO_ROOT / "changelog"

RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\S+)\s*$", re.M)
INDEX_ROW = re.compile(r"^\| (\d+\.\d+\.\d+) \| (\S+) \| \[changelog/(\S+?)\]\(changelog/(\S+?)\) \|$", re.M)


def _text() -> str:
    return CHANGELOG.read_text(encoding="utf-8")


def test_the_changelog_holds_at_most_one_released_version():
    """回転を忘れた版が 2 つ目として残ると、その次のリリースでも同じことが起きる。
    「累積しない」という性質は、毎回きっちり 1 つに戻すことでしか保てない。"""
    found = RELEASE_HEADING.findall(_text())
    assert len(found) <= 1, (
        "CHANGELOG.md に確定した版が複数あります "
        f"({', '.join(v for v, _ in found)})。"
        "リリース時に前の版を changelog/<version>.md へ送ってください"
    )


def test_the_unreleased_section_is_still_there():
    """Keep a Changelog の `[Unreleased]` は次のエントリの置き場である。回転の実装が
    ここまで持っていくと、次に書く人は行き先を失う。"""
    assert "## [Unreleased]" in _text()


def test_every_indexed_version_has_a_file():
    rows = INDEX_ROW.findall(_text())
    assert rows, "過去版の索引が空です（0.1.0 以降が 1 件も載っていない）"
    for version, _date, link_text, link_target in rows:
        assert link_text == link_target, (
            f"索引 {version} のリンク表記と行き先が食い違っています: {link_text} != {link_target}"
        )
        assert (ARCHIVE / link_target).is_file(), (
            f"索引が changelog/{link_target} を指していますが、そのファイルがありません"
        )


def test_every_archived_file_is_in_the_index():
    """索引に無いファイルは、リポジトリを開いた人からは到達できない — 移したが
    索引に足し忘れた版は、消したのと読み手にとっては同じである。"""
    indexed = {target for _v, _d, _t, target in INDEX_ROW.findall(_text())}
    on_disk = {p.name for p in ARCHIVE.glob("*.md")}
    assert on_disk - indexed == set(), (
        f"changelog/ にあるのに索引へ載っていない版があります: {sorted(on_disk - indexed)}"
    )


def test_each_archived_file_holds_exactly_the_version_it_is_named_for():
    """ファイル名と中身がずれると、`/wikicommit-update` が版の範囲でファイルを選ぶ
    手順（Step 9）が誤ったものを読む — そして出力は一見正常に見える。"""
    for path in sorted(ARCHIVE.glob("*.md")):
        found = RELEASE_HEADING.findall(path.read_text(encoding="utf-8"))
        assert len(found) == 1, f"{path.name}: 版の見出しが {len(found)} 個あります（1 個であるべき）"
        assert found[0][0] == path.stem, (
            f"{path.name}: 中身の版が {found[0][0]} でファイル名と一致しません"
        )


def test_the_index_is_ordered_newest_first():
    """CHANGELOG 本体が新しい順である以上、索引だけ逆順だと読み手がその場で並べ替える。"""
    versions = [tuple(int(n) for n in v.split(".")) for v, _d, _t, _g in INDEX_ROW.findall(_text())]
    assert versions == sorted(versions, reverse=True), f"索引が新しい順になっていません: {versions}"


def test_the_update_skill_reads_only_the_versions_it_needs():
    """回転の目的は読み込み量を版の差に比例させることであり、Step 9 が全ファイルを
    読むならファイルを分けた意味が無い。"""
    text = (REPO_ROOT / ".claude" / "skills" / "wikicommit-update" / "SKILL.md").read_text(
        encoding="utf-8")
    assert "changelog/" in text
