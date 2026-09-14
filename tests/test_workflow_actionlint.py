"""`actionlint` を配布ワークフローテンプレートと自リポジトリのワークフローに掛ける（Issue #862）。

Issue #830 は、`run:` 本文に literal で書いた中身の無い式展開 1 行が
`review-issue-close-sync.yml` 全体をパースエラーにし、そのワークフローが
`issues: closed` で一度も起動していなかったという不具合を直した。再発防止に
追加した `test_workflow_template_expressions.py` が見るのは、**その 1 つの
失敗クラスだけ**である。配布テンプレートは `_root_outputs.py` の
`update: overwrite`（Issue #712）なので、構文エラーはこのリポジトリの外へ
増幅して届く — 上乗せの網として上流のリンタを掛ける。

**既存テストを置き換えず併存させる。** `actionlint` は空の式を含む構文エラー
全般を見るため機能的には上位互換だが、バイナリが無い環境では何も残らない。
既存テストは依存ゼロの最低保証として常に走り、Issue #830 が実際に踏んだクラス
だけは `actionlint` の有無に関わらず必ず止まる。

**バイナリ不在時は skip する。** skip は「入れていない環境では黙って通る」
ことを意味するが、その穴は上の最低保証と、`main` に到達する前に PR の CI が
必ず 1 回は全クラスを検査することの 2 つで塞がれている（CI では必須・
ローカルでは任意、という非対称は Issue #862 で意図して選んだ）。残る穴は 1 つ
だけで、CI が使えずローカル検証へ落ちた回（課金枠切れ等）のうち、**バイナリを
入れていない環境**である — ローカル検証の手順自体は `actionlint` が `PATH` に
あれば併せて実行するため（Issue #938）、入れてあればその回も CI と等価になる。

**CI ではこれらのテストも実際に走る。** `test.yml` は取得した actionlint を
`RUNNER_TEMP` へ置いて `PATH` に載せるため `shutil.which()` が見つける。作業
ツリーへ `./actionlint` として落とすと **CI でも skip** され、この parametrize
だけが持つ範囲（`*.yaml` 拡張子のワークフロー。CI の明示 glob は `*.yml` しか
拾わない）がどこからも検査されなくなるうえ、このテスト自身が一度も実行されない
まま `main` へ入る。

**検査対象の探索は `_workflows.py` が持つ**（既存テストと共有）。対象が 0 件に
なると parametrize は「全部通った」ように見えるが、同じ集合に対する
`test_workflow_template_expressions.py` の 2 つの「見つかったか」ガードが
それを固定するため、ここでは重ねて持たない。

**`shellcheck` / `pyflakes` が `PATH` にあると `actionlint` は `run:` 本文を
それらにも掛ける**ため、ローカル（通常は不在）と CI（`ubuntu-latest` は
`shellcheck` を同梱）で結果が割れる。Issue #862 の起票時の実測は当時の 3 本に
対して差が出なかったが、**同 Issue の実装中に 1 度実際に割れた** — CI へ
`actionlint` 自身の取得を足した行が `SC2016`（単一引用符の中の `$` は展開
されない）を踏み、ローカルは緑・CI だけ赤という形になった。`bash -c '...'`
をシェル関数に置き換えて解消してある。**この非対称はローカル検証だけでは
見えない**ので、`.github/workflows/` の `run:` を触ったときは `shellcheck` を
`PATH` に置いて `actionlint` を回すこと。
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from _workflows import workflow_files

ACTIONLINT = shutil.which("actionlint")

pytestmark = pytest.mark.skipif(
    ACTIONLINT is None,
    reason=(
        "actionlint が PATH にありません。CI では必須・ローカルでは任意です"
        "（Issue #862）。入れる場合は "
        "https://github.com/rhysd/actionlint/releases から取得してください — "
        "CI が固定している版は .github/workflows/test.yml の ACTIONLINT_VERSION が"
        "正本であり、ここに版を書き写すと bump のたびに古い版の導入を案内する"
        "（ローカルと CI で結果が割れる、まさにこのファイルが警告している形になる）"
    ),
)


@pytest.mark.parametrize("workflow", workflow_files(), ids=lambda p: p.name)
def test_workflow_passes_actionlint(workflow: Path):
    assert ACTIONLINT is not None  # pytestmark が保証する（型のためだけの再確認）
    result = subprocess.run(
        [ACTIONLINT, "-no-color", str(workflow)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"{workflow} が actionlint の検査に通りません:\n"
        f"{result.stdout}{result.stderr}"
        "\nGitHub Actions は構文エラーをファイル全体のパースエラーとして扱い、"
        "ワークフローは startup_failure で一度も起動しなくなります"
        "（ジョブ 0 件でログも残らない。Issue #830）。"
        "配布テンプレートの場合、壊れたまま再 init した全リポジトリへ"
        "黙って上書き配布されます（Issue #712）。"
    )
