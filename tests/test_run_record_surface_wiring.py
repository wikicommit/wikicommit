"""`check_run_records.py` が出す行を `/wikicommit-status` が全部読んでいることを検証する（Issue #835）。

同スクリプトは 3 種の行（`LAST_RUN:` / `INCOMPLETE_RUN:` / `MISSING_PASS:`）と
`SUMMARY: runs=, incomplete=, missing_pass=` を出すが、**`MISSING_PASS:` は
`wikicommit-status/SKILL.md` に 1 度も現れず、計算されて捨てられていた** —
Step 14 の説明も Step 17 の表示ブロックも `LAST_RUN:` と `INCOMPLETE_RUN:` の
2 つしか挙げていなかった。

落ちていたのはパスごとの打点（Issue #797）が答えようとした 2 つの問いのうち
片方、すなわち「パスが丸ごと飛ばされたか」の側である。これは Issue #406 /
#452 / #474 が 3 度繰り返した失敗クラス（長い多段フローの末尾で手順が落ちる）に
対する検出そのもので、3 件とも公開済みの Wiki を人が手で監査して初めて
見つかっている。

**書く側と読む側が別ファイルにあり、片方だけを足しても何も壊れない** —
スクリプトが新しい行を出し始めても、SKILL.md がそれを読まなければ出力が
静かに捨てられるだけで、テストも lint も緑のままになる。パイロットの観察項目に
挙げられていた行が黙って発火しなかった、というのが実際の現れ方だった。
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
    / "scripts" / "check_run_records.py"
)
STATUS_SKILL = REPO_ROOT / ".claude" / "skills" / "wikicommit-status" / "SKILL.md"


def _stdout_prefix(call: ast.Call) -> str | None:
    """The `PREFIX:` this `print()` writes to stdout, or None.

    Whether a call goes to stderr is read off its `file=` keyword rather than
    off the text of the line, and no prefix is exempted by name. Both of those
    were holes: a `WARNING:` line moved to stdout would have been let through
    the wiring requirement by an allowlist, and a `print(` wrapped across lines
    with `file=sys.stderr` on its own line would have been read as stdout. The
    first is this test failing to catch the very bug it is for.
    """
    if not (isinstance(call.func, ast.Name) and call.func.id == "print"):
        return None
    dest = next((kw.value for kw in call.keywords if kw.arg == "file"), None)
    if dest is not None and ast.unparse(dest) == "sys.stderr":
        return None
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        head = first.value
    elif isinstance(first, ast.JoinedStr) and first.values:
        lead = first.values[0]
        if not (isinstance(lead, ast.Constant) and isinstance(lead.value, str)):
            return None
        head = lead.value
    else:
        return None
    prefix, sep, _ = head.partition(":")
    if not sep or not prefix or not all(c.isupper() or c == "_" for c in prefix):
        return None
    return prefix


def _emitted_prefixes() -> set[str]:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    found = (
        _stdout_prefix(node) for node in ast.walk(tree) if isinstance(node, ast.Call)
    )
    return {prefix for prefix in found if prefix is not None}


def test_every_emitted_line_is_read_by_the_status_skill():
    skill = STATUS_SKILL.read_text(encoding="utf-8")
    emitted = _emitted_prefixes()
    # 保険: 走査が壊れて空集合になると、このテストは無言で通る。
    assert {"LAST_RUN", "INCOMPLETE_RUN", "MISSING_PASS", "SUMMARY", "NOTE"} <= emitted, (
        f"check_run_records.py の print() 走査が想定より少ない接頭辞しか拾えていません: {sorted(emitted)}"
    )

    unread = sorted(prefix for prefix in emitted if f"{prefix}:" not in skill)
    assert not unread, (
        f"{SCRIPT.name} が出力する行のうち {unread} を "
        f"{STATUS_SKILL} が 1 度も参照していません。"
        "スクリプトが計算した結果がそのまま捨てられます（Issue #835）。"
        "Step 14 の説明と Step 17 の表示ブロックの両方に足してください。"
    )


def test_status_skill_reads_the_missing_pass_count_and_lines():
    """行の存在だけでなく、表示ブロックの行と `SUMMARY:` の読み取りまで固定する。

    上のテストは `MISSING_PASS:` という文字列がファイルのどこかにあれば通るため、
    Step 14 の説明にだけ書いて Step 17 の表示に足し忘れる、という中途半端な
    配線を素通りさせる。表示されない行は、運用者にとっては配線されていないのと
    同じである。
    """
    skill = STATUS_SKILL.read_text(encoding="utf-8")
    assert "Runs that skipped a pass:" in skill, (
        "Step 17 の表示ブロックに `MISSING_PASS:` を読む行がありません（Issue #835）。"
    )
    assert "missing_pass=" in skill, (
        "Step 17 が `SUMMARY:` の `missing_pass=` を読んでいません（Issue #835）。"
    )
