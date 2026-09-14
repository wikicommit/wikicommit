"""ワークフローの式展開（`${{ ... }}`）が空になっていないことを検証する（Issue #830）。

GitHub Actions は **`run:` の本文を実行前に式展開する**。したがってその中の
`#` 行はシェルコメントであっても、展開の時点では単なる文字列であり展開対象に
なる。中身の無い式（`${{ }}`）を 1 つ書くと式パーサが落ち、**ファイル全体が
読み込めなくなる** — ジョブが 0 件の `startup_failure` になるため、ログも
残らず、Actions の一覧に出る run 名はワークフローの `name:` ではなくファイル
パスになる（`name:` を読めていないため）。

実際に `review-issue-close-sync.yml` の 332 行目で起きた（Issue #764 が
導入、0.5.0 で配布）。「この値は式展開もシェル展開も通らない」ことを説明する
ために `${{ }}` を literal で書いたコメントが、そのワークフロー全体を
起動不能にしていた。しかも `_root_outputs.py` の `update: overwrite`
（Issue #712）により、再 init したリポジトリへ黙って上書き配布される。

**禁じるのは綴りではなく「空の式」である。** YAML コメント（`#` が行頭から
始まる行）に書かれた `${{ }}` は YAML パーサが落とすため Actions は見ておらず
無害なので、ここでは `yaml.safe_load` 後の**値**のみを走査する。中身のある式
（`deploy.yml` の `${{ steps.pages.outputs.base_url }}` 等）も当然対象外。

走査対象は 2 つのディレクトリにまたがり、**公開境界がその間を通る** — 配布
テンプレート（`.claude/skills/`）は公開サブセットに入るが、`.github/` は恒久除外
（`dev/scripts/snapshot_push.sh` の `FORBIDDEN_PATHS`）である。したがって後者が
公開側で「無い」ことは正常だが、**開発リポジトリでリネーム・移動されたときの
見え方と区別が付かない** — `dev/publication-scope.md` §5 が「ファイルが無いこと
自体は判定に使わない（リネームと見分けが付かず、リネームを捕まえることこそ
ガードの目的）」と定めるとおり、判定は `_publication.is_development_repository()`
に委ね、下の 2 つのガードをディレクトリごとに分けて持つ。

走査対象の探索そのものは `_workflows.py` が持つ（Issue #862）— 同じ 2 ディレクトリを
`test_workflow_actionlint.py` も歩くようになり、2 つの写しが drift すると「狭い方の
ガードは緑のまま、広い方だけが黙ってファイルを見なくなる」という最悪の形で現れるため。
"""

from pathlib import Path

import pytest
import yaml
from _publication import skip_unless_development_repository
from _workflows import REPO_WORKFLOWS, TEMPLATE_WORKFLOWS, names_in, workflow_files

EXPRESSION_OPEN = "${{"
EXPRESSION_CLOSE = "}}"


def _iter_scalars(node, path: str = ""):
    """YAML ツリー内の全文字列スカラーを (パス, 値) で列挙する。

    コメントは `yaml.safe_load` の時点で消えるため、ここに現れるのは Actions が
    実際に読む値だけになる。
    """
    if isinstance(node, str):
        yield path or "<root>", node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_scalars(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_scalars(value, f"{path}[{index}]")


def _empty_expressions(value: str) -> list[str]:
    """値の中の、空または閉じられていない `${{ ... }}` を列挙する。"""
    problems: list[str] = []
    start = value.find(EXPRESSION_OPEN)
    while start != -1:
        end = value.find(EXPRESSION_CLOSE, start + len(EXPRESSION_OPEN))
        if end == -1:
            problems.append(value[start : start + 40])
            break
        inner = value[start + len(EXPRESSION_OPEN) : end]
        if not inner.strip():
            problems.append(value[start : end + len(EXPRESSION_CLOSE)])
        start = value.find(EXPRESSION_OPEN, end + len(EXPRESSION_CLOSE))
    return problems


@pytest.mark.parametrize("workflow", workflow_files(), ids=lambda p: p.name)
def test_workflow_has_no_empty_expression(workflow: Path):
    document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    findings: list[str] = []
    for key_path, value in _iter_scalars(document):
        for snippet in _empty_expressions(value):
            findings.append(f"{key_path}: {snippet!r}")

    assert not findings, (
        f"{workflow} に中身の無い（または閉じられていない）式展開があります: "
        + " / ".join(findings)
        + "。GitHub Actions はこれをファイル全体のパースエラーとして扱い、"
        "ワークフローは startup_failure で一度も起動しなくなります（Issue #830）。"
        "`run:` 本文の `#` 行はシェルコメントですが展開はされるので、"
        "式そのものを literal で書かず散文で言い換えてください。"
    )


def test_template_workflow_files_were_found():
    # パス定数が壊れた場合、上の parametrize は 0 件になり「全部通った」ように
    # 見える（テストとして無言で消える）。対象が実際にあることを固定する。
    assert TEMPLATE_WORKFLOWS.is_dir(), (
        f"配布ワークフローテンプレートのディレクトリがありません: {TEMPLATE_WORKFLOWS}"
    )
    names = names_in(TEMPLATE_WORKFLOWS)
    assert {"deploy.yml", "review-issue-close-sync.yml"} <= names, (
        f"配布ワークフローテンプレートが見つかりません: {sorted(names)}"
    )


def test_repository_workflow_files_were_found():
    # **2 つのディレクトリを 1 つの名前集合に畳んで見ない。** 畳むと上の 2 本
    # （配布テンプレート側）だけで条件が満たされるため、`.github/workflows/` が
    # 消えても緑のままになり、`workflow_files()` の `is_dir()` スキップと合わせて
    # このリポジトリ自身のワークフローが黙って検査対象から外れる — パス定数が
    # 壊れたときに無言で消える、というこのガードが防ぐはずの形そのものである。
    skip_unless_development_repository(".github/workflows/ is not published")
    assert REPO_WORKFLOWS.is_dir(), (
        f"このリポジトリのワークフローディレクトリがありません: {REPO_WORKFLOWS}"
    )
    names = names_in(REPO_WORKFLOWS)
    assert names, (
        f"{REPO_WORKFLOWS} にワークフローが 1 件もありません。"
        "検査対象が黙って 0 件になると、このテストは「全部通った」ように見えます"
    )
