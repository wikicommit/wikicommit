#!/usr/bin/env python3
"""set_frontmatter_field.py — frontmatter 内の特定フィールドを部分書き換えする共有スクリプト。

pyyaml で frontmatter ブロック全体を再シリアライズすると、インデント・クォート・
キー順序が変わってしまうため、対象フィールドの行のみを正規表現で置換する
（本文・他フィールドの書式は一切変更しない）。

このパターンはもともと以下の3箇所に独立実装として重複していた（Issue #371）:
  - `.claude/skills/wikicommit-review/SKILL.md` Step 5（review_status を無条件で reviewed に上書き）
  - `.github/workflows/review-issue-close-sync.yml`（review_status が pending の場合のみ reviewed に上書き）
  - `.claude/skills/wikicommit-remove/scripts/remove_page.py`（status/removed_at 等、複数フィールドを追加）

本スクリプトは前者2つを置き換える共有実装として `.wikicommit/scripts/` に切り出した
（`_frontmatter.py` / `_wikilink.py` と同じ「一つの実装を全呼び出し元が import/呼び出しする」
方針）。`remove_page.py` は Skill 固有スクリプトのまま据え置き、対応スコープ外とする
（Issue #371 完了条件を参照）。

Usage:
    python .wikicommit/scripts/set_frontmatter_field.py <page> \\
        --set KEY=VALUE [--set KEY=VALUE ...] [--require KEY=VALUE]

--set KEY=VALUE
    frontmatter ブロック内の `KEY: ...` 行を VALUE に置換する（複数指定可）。
    既存の行があれば置換、なければブロック末尾に追加する。VALUE は書き込む生の
    YAML スカラー値をそのまま渡す（クォートが必要な場合は呼び出し側で含めること。
    例: --set 'removed_at="2026-07-29"'）。

--require KEY=VALUE
    書き換えを実行する前に、frontmatter 内の現在の KEY の値が VALUE と一致するかを
    確認する（前後のクォート " / ' の有無は無視して比較する）。一致しなければ
    書き換えを行わず SKIP を報告して終了する（呼び出し元が「既に別の値になって
    いるので何もしない」を判断できるようにするための正常系であり、エラーでは
    ない）。省略した場合は無条件で --set を適用する。

Exit code:
    0 = 成功（実際に書き換えた場合、または --require 不一致で SKIP した場合）
    1 = <page> が存在しない / frontmatter ブロックが見つからない / 引数の形式が不正
"""

import argparse
import re
import sys
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^(---\r?\n)(.*?)((?:\r?\n)?---\r?\n?)", re.DOTALL)


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _current_value(yaml_block: str, key: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(key)}:(.*)$", re.MULTILINE)
    m = pattern.search(yaml_block)
    if m is None:
        return None
    return _strip_quotes(m.group(1))


def _upsert_field(yaml_block: str, key: str, value: str) -> str:
    """yaml_block 内の `key: ...` 行を置換、なければ末尾に追加する。"""
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    line = f"{key}: {value}"
    if pattern.search(yaml_block):
        # 文字列として渡すと value 中の "\1" 等がグループ参照として解釈され
        # re.error を招くため、関数として渡してリテラル置換にする。
        return pattern.sub(lambda _m: line, yaml_block, count=1)
    return yaml_block.rstrip("\r\n") + f"\n{line}"


def parse_kv(raw: str, flag: str) -> tuple[str, str] | None:
    """Parse a KEY=VALUE argument. Returns None (after printing an ERROR) on
    malformed input, so callers can propagate a normal `return 1` from
    main() instead of exiting mid-parse."""
    if "=" not in raw:
        print(f"ERROR: {flag} は KEY=VALUE 形式で指定してください: {raw!r}", file=sys.stderr)
        return None
    key, _, value = raw.partition("=")
    key = key.strip()
    if not key:
        print(f"ERROR: {flag} のキーが空です: {raw!r}", file=sys.stderr)
        return None
    return key, value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite specific frontmatter fields without re-serializing the whole block."
    )
    parser.add_argument("page", help="Path to the wiki page (relative to the repository root)")
    parser.add_argument(
        "--set", dest="sets", action="append", default=[], metavar="KEY=VALUE",
        help="Field to add or overwrite (repeatable)",
    )
    parser.add_argument(
        "--require", dest="require", default=None, metavar="KEY=VALUE",
        help="Only proceed if the field's current value matches; otherwise SKIP",
    )
    args = parser.parse_args()

    if not args.sets:
        print("ERROR: --set を1件以上指定してください", file=sys.stderr)
        return 1

    set_pairs = [parse_kv(raw, "--set") for raw in args.sets]
    if any(pair is None for pair in set_pairs):
        return 1

    require_pair = None
    if args.require is not None:
        require_pair = parse_kv(args.require, "--require")
        if require_pair is None:
            return 1

    page_path = Path(args.page)
    if not page_path.is_file():
        print(f"ERROR: {args.page}: ファイルが存在しません", file=sys.stderr)
        return 1

    with page_path.open(encoding="utf-8-sig", newline="") as f:
        content = f.read()

    m = FRONTMATTER_RE.match(content)
    if not m:
        print(f"ERROR: {args.page}: frontmatter ブロックが見つかりません", file=sys.stderr)
        return 1

    yaml_block = m.group(2)
    delimiter = m.group(3)

    if require_pair is not None:
        req_key, req_value = require_pair
        current = _current_value(yaml_block, req_key)
        if current is None or current != _strip_quotes(req_value):
            print(
                f"SKIP: {args.page}: {req_key} is not {req_value!r} "
                f"(current: {current!r}); no changes made"
            )
            return 0

    for key, value in set_pairs:
        yaml_block = _upsert_field(yaml_block, key, value)

    if not re.match(r"^\r?\n", delimiter):
        yaml_block += "\n"

    content = content[: m.start(2)] + yaml_block + content[m.end(2):]
    with page_path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)

    for key, value in set_pairs:
        print(f"OK: {args.page}: {key} -> {value}")
    print(f"SUMMARY: fields_set={len(set_pairs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
