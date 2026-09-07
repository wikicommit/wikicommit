"""経路 A の Close コメントがレビュー記録に載ることを検証する（Issue #762）。

Issue #740 は追跡 Issue の主たる依頼を「このページから何を受け取ったかを一言書いて
Close する」に変えた。その一言は `review_status` が 2 値であるがゆえにフィールドには
収まらない産物であり、`.wikicommit/review/` の記録本文だけが受け皿になる。ところが
経路 B（`/wikicommit-review`）は `--note` で渡す一方、**経路 A（GitHub 上で Close。
Issue #313 が主経路として設計したほう）は渡しておらず、同じ産物が入口によって残ったり
残らなかったりしていた**。

この経路は実際に GitHub 上で追跡 Issue を Close するまで顕在化しないため、テンプレートの
静的な検証と、埋め込まれた選別ロジックの実行としてここで固定する。とくに:

- コメント本文は第三者が書ける自由記述であり、このワークフローがファイル冒頭で全ステップに
  課している方針（`github.event.*` を `run:` へ `${{ }}` で直接展開しない）と同じ理由で、
  シェルのコマンドラインに一度も載せてはならない。ファイル経由の `--note-file` がその担保である
- コメントが 1 件も無いまま Close された場合、記録ステップは失敗せず本文なしの記録を書く
  （＝この変更以前とまったく同じ結果になる）。沈黙して閉じるのは正常な閉じ方である
- 「最新」の判定を API の並び順に委ねない。`GET .../issues/{issue_number}/comments` が
  受け付けるのは `since` / `per_page` / `page` だけで、`sort` / `direction` は
  リポジトリ単位のエンドポイントのパラメータである — 渡しても無視され、応答は
  ID 昇順（古い順）になる
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

TEMPLATES = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
SYNC_YML = TEMPLATES / "workflows" / "review-issue-close-sync.yml"

CAPTURE_STEP = "Capture the closing comment"
RECORD_STEP = "Record the human review"


def _steps() -> list[dict]:
    workflow = yaml.safe_load(SYNC_YML.read_text(encoding="utf-8"))
    return list(workflow["jobs"].values())[0]["steps"]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"ステップ {name!r} が review-issue-close-sync.yml にありません")


def _embedded_selector() -> str:
    """`Capture the closing comment` に埋め込まれた Python を取り出す。

    文面をテストが複製すると、ワークフロー側だけが変わったときに黙って乖離する
    （このリポジトリが `_wikilink.py` 等で繰り返し踏んできた形）。実際に走る
    プログラムそのものを取り出して実行する。
    """
    run = _step(CAPTURE_STEP)["run"]
    match = re.search(r"<<'PY'\n(.*?)\n\s*PY\n", run, re.DOTALL)
    assert match, "埋め込まれた Python ヒアドキュメントが見つかりません"
    return match.group(1)


def _select(tmp_path: Path, comments: list[dict], login: str) -> str | None:
    comments_json = tmp_path / "comments.json"
    comments_json.write_text(json.dumps(comments), encoding="utf-8")
    note = tmp_path / "note.txt"
    result = subprocess.run(
        [sys.executable, "-", str(comments_json), str(note)],
        input=_embedded_selector(),
        capture_output=True,
        text=True,
        env={"REVIEWER_LOGIN": login, "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return note.read_text(encoding="utf-8") if note.exists() else None


def test_the_capture_step_runs_before_the_record_step():
    names = [step.get("name") for step in _steps()]
    assert names.index(CAPTURE_STEP) < names.index(RECORD_STEP)


def test_the_record_step_reads_the_captured_note():
    record = _step(RECORD_STEP)
    assert record["env"].get("NOTE_FILE") == "${{ steps.note.outputs.note_file }}"
    assert "--note-file" in record["run"]


def test_the_comment_body_never_reaches_a_command_line():
    """本文はファイル経由でのみ渡る。`--note` に渡す形へ書き換えられていないこと。"""
    capture = _step(CAPTURE_STEP)["run"]
    record = _step(RECORD_STEP)["run"]
    assert "--note-file" in record
    assert re.search(r"--note(?!-file)\b", record) is None, (
        "本文を --note でコマンドラインに載せています。自由記述であり、"
        "このワークフローが全ステップに課している展開禁止の方針に反します"
    )
    # 本文を出力値に載せると `${{ steps.*.outputs.* }}` として再展開される経路ができる。
    assert "note_file=" in capture and "note=" not in capture.replace("note_file=", "")


def test_the_per_issue_endpoint_is_not_asked_to_sort(tmp_path):
    """`sort` / `direction` はこのエンドポイントに存在しない。

    `GET /repos/{owner}/{repo}/issues/{issue_number}/comments` が受け付けるのは
    `since` / `per_page` / `page` だけで、`sort` / `direction` は**リポジトリ単位の**
    エンドポイント（`/repos/{owner}/{repo}/issues/comments`）のパラメータである。
    渡しても黙って無視され、応答は既定の ID 昇順（＝最も古いものが先頭）になる。
    順序をサーバーに委ねると、先頭で一致したものが「最新」ではなくなる。
    """
    capture = _step(CAPTURE_STEP)["run"]
    assert "direction=desc" not in capture, (
        "この API は direction を受け付けない。渡すと desc を得たつもりで昇順を読むことになる"
    )
    assert "-f sort=" not in capture
    # 1 ページに収まらない Issue では、昇順の 1 ページ目は「最も古い 100 件」になる。
    assert "--paginate" in capture


def test_the_closer_s_latest_comment_is_selected_regardless_of_api_order(tmp_path):
    """案 (b)。順序は API ではなくこちらが `created_at` で決める。

    フィクスチャは API が実際に返す順序（古い順）で並べてある — 先頭で一致した
    ものを採る実装であれば、ここで最も古いコメントを拾って落ちる。
    """
    note = _select(
        tmp_path,
        [
            {
                "user": {"login": "octocat"},
                "body": "あとで読みます",
                "created_at": "2026-09-01T10:00:00Z",
                "id": 1,
            },
            {
                "user": {"login": "someone-else"},
                "body": "別件のコメント",
                "created_at": "2026-09-02T10:00:00Z",
                "id": 2,
            },
            {
                "user": {"login": "octocat"},
                "body": "この街に川が多いことを初めて知りました。",
                "created_at": "2026-09-03T10:00:00Z",
                "id": 3,
            },
        ],
        "octocat",
    )
    assert note == "この街に川が多いことを初めて知りました。\n"


def test_comments_split_across_pages_are_all_considered(tmp_path):
    """`gh api --paginate` は各ページの JSON 配列を区切りなく連結して書き出す。

    1 ページ目だけを読むと、昇順である以上「最も古い 100 件」しか見ないことになる。
    """
    page1 = [{"user": {"login": "octocat"}, "body": "古い方", "created_at": "2026-09-01T00:00:00Z", "id": 1}]
    page2 = [{"user": {"login": "octocat"}, "body": "受け取ったもの", "created_at": "2026-09-04T00:00:00Z", "id": 2}]
    comments_json = tmp_path / "comments.json"
    comments_json.write_text(json.dumps(page1) + "\n" + json.dumps(page2) + "\n", encoding="utf-8")
    note = tmp_path / "note.txt"
    result = subprocess.run(
        [sys.executable, "-", str(comments_json), str(note)],
        input=_embedded_selector(),
        capture_output=True,
        text=True,
        env={"REVIEWER_LOGIN": "octocat", "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert note.read_text(encoding="utf-8") == "受け取ったもの\n"


def test_a_comment_by_someone_else_is_not_mistaken_for_the_closer_s(tmp_path):
    """案 (a)（Close 直前の最後のコメント）を採らなかった理由そのもの。"""
    note = _select(
        tmp_path,
        [
            {
                "user": {"login": "octocat"},
                "body": "受け取ったもの",
                "created_at": "2026-09-01T00:00:00Z",
                "id": 1,
            },
            {
                "user": {"login": "someone-else"},
                "body": "直前に書かれた無関係なコメント",
                "created_at": "2026-09-02T00:00:00Z",
                "id": 2,
            },
        ],
        "octocat",
    )
    assert note == "受け取ったもの\n"


def test_closing_without_a_comment_leaves_no_note(tmp_path):
    """沈黙して閉じるのは正常な閉じ方であり、失敗ではない。"""
    assert _select(tmp_path, [], "octocat") is None
    assert _select(tmp_path, [{"user": {"login": "someone-else"}, "body": "x"}], "octocat") is None
    assert _select(tmp_path, [{"user": {"login": "octocat"}, "body": "   \n  "}], "octocat") is None


def test_a_failed_fetch_degrades_to_a_record_with_no_body():
    """このステップは実行を落としてはならない。

    review_status の書き換えは済んでいるがコミットはまだであるため、ここで job が
    落ちると Issue は Close 済み・ページは pending のまま残り、この workflow は
    `issues: closed` でしか起動しないので再試行の経路が無い。
    """
    capture = _step(CAPTURE_STEP)["run"]
    assert capture.count("set +e") == 2, "gh api と選別スクリプトの両方を守る必要があります"
    assert capture.count("exit 0") == 2
    assert "::warning::" in capture


def test_shell_metacharacters_in_a_comment_survive_verbatim(tmp_path):
    """本文がシェルを一度も経ないことの結果: 中身がそのまま記録に載る。"""
    body = "`id` $(touch /tmp/pwned) ${HOME} \"quoted\" 'single'"
    note = _select(tmp_path, [{"user": {"login": "octocat"}, "body": body}], "octocat")
    assert note == body + "\n"
