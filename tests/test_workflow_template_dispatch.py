"""配布ワークフローテンプレート間の結合を検証する（Issue #544）。

`review-issue-close-sync.yml` のレビュー自動マージは既定の `GITHUB_TOKEN` による
push であり、GitHub Actions の仕様上そのままでは `deploy.yml` の `on: push` を
起動しない（無限ループ防止のための意図的な挙動）。そのため `main` は
`review_status: reviewed` なのに公開サイトだけ未レビューバナーのまま取り残される
という、気づく手段のない食い違いが起きていた（`wikicommit/ai-driven-dev-wiki` で
実地確認）。

対応として `review-issue-close-sync.yml` が `gh workflow run deploy.yml` で
`deploy.yml` を明示的に dispatch する。この経路は 2 つの独立したテンプレート
ファイルにまたがる暗黙の契約に依存しており、どちらか一方を編集しただけで静かに
壊れる:

- `deploy.yml` が `workflow_dispatch` トリガーを宣言していること
  （無いと `gh workflow run` が失敗する）
- `deploy.yml` の `build` ジョブが `workflow_dispatch` 起動時にも実行されること
  （Issue #351 の `if:` はデフォルトブランチへの push に絞り込むため、
  `workflow_dispatch` の分岐が抜けると dispatch しても何もビルドされない）
- `review-issue-close-sync.yml` が `actions: write` を要求していること
  （無いと dispatch が 403 で失敗する）

いずれも実際に GitHub 上でレビュー追跡 Issue を Close するまで顕在化しないため、
テンプレートの静的な検証としてここで固定する。
"""

from pathlib import Path

import yaml

TEMPLATES = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
DEPLOY_YML = TEMPLATES / "workflows" / "deploy.yml"
SYNC_YML = TEMPLATES / "workflows" / "review-issue-close-sync.yml"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    # YAML 1.1 では裸の `on:` が真偽値 True にパースされる（PyYAML の既定挙動）。
    return workflow.get("on", workflow.get(True))


def test_deploy_declares_workflow_dispatch():
    triggers = _triggers(_load(DEPLOY_YML))
    assert "workflow_dispatch" in triggers, (
        "deploy.yml が workflow_dispatch トリガーを宣言していません。"
        "review-issue-close-sync.yml の `gh workflow run deploy.yml` が失敗します（Issue #544）。"
    )


def test_deploy_build_job_runs_on_workflow_dispatch():
    build_if = _load(DEPLOY_YML)["jobs"]["build"]["if"]
    # 単に "workflow_dispatch" という文字列を含むかどうかでは不十分:
    # `github.event_name != 'workflow_dispatch' && ...` のように否定形へ書き換えられても
    # 素通りしてしまい、dispatch しても build がスキップされる（＝このテストが防ぎたい
    # 状態そのもの）まま緑になる。許可の分岐そのものを固定する。
    assert "github.event_name == 'workflow_dispatch'" in build_if, (
        "deploy.yml の build ジョブの if: が workflow_dispatch 起動を許可していません。"
        "dispatch しても何もビルドされません（Issue #544 / #351）。"
    )


def test_sync_requests_actions_write_permission():
    permissions = _load(SYNC_YML)["permissions"]
    assert permissions.get("actions") == "write", (
        "review-issue-close-sync.yml が actions: write を要求していません。"
        "`gh workflow run` が 403 で失敗します（Issue #544）。"
    )


def test_sync_dispatches_deploy_after_merge():
    steps = _load(SYNC_YML)["jobs"]["sync"]["steps"]
    names = [step.get("name") for step in steps]
    dispatch_index = next(
        (i for i, step in enumerate(steps) if "gh workflow run deploy.yml" in (step.get("run") or "")),
        None,
    )
    assert dispatch_index is not None, (
        "review-issue-close-sync.yml に `gh workflow run deploy.yml` を実行するステップがありません（Issue #544）。"
    )
    dispatch = steps[dispatch_index]
    merge_index = names.index("Auto-merge on quality pass")
    # マージが実際に起きたときだけ dispatch する（品質ゲート失敗時に走らせない）。
    assert dispatch["if"] == steps[merge_index]["if"], (
        "Pages 再ビルドの dispatch ステップの if: が自動マージステップと一致していません。"
        "マージされていないのにビルドを起動する（またはその逆の）恐れがあります。"
    )
    # if: の一致だけでは「マージ成功時のみ dispatch する」を保証できない — その保証は
    # step-level if: に暗黙で AND される success()（＝先行ステップが全て成功したときのみ実行）
    # に由来するため、dispatch ステップが自動マージステップより後ろにあることが前提になる。
    # 順序が入れ替わると、マージ前の HEAD をビルドしてしまい（＝公開サイトは未レビュー
    # バナーのまま）Issue #544 の症状がそのまま再現するので、順序自体も固定する。
    assert dispatch_index > merge_index, (
        "Pages 再ビルドの dispatch ステップが自動マージステップより前に置かれています。"
        "マージ前の HEAD をビルドしてしまい、Issue #544 の症状が再現します。"
    )
    # deploy.yml を配布しない構成（--quartz-pages を選ばなかった場合）では何もしない。
    assert ".github/workflows/deploy.yml" in dispatch["run"], (
        "deploy.yml の存在確認なしに dispatch しています。--quartz-pages を選ばなかったリポジトリでも"
        "review-issue-close-sync.yml は配布されるため（Issue #335）、無条件 dispatch は失敗します。"
    )
