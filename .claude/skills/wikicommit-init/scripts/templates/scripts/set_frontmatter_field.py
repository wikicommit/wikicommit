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
        [--set KEY=VALUE ...] [--unset KEY ...] [--require KEY=VALUE]

--set KEY=VALUE
    frontmatter ブロック内の `KEY: ...` 行を VALUE に置換する（複数指定可）。
    既存の行があれば置換、なければブロック末尾に追加する。VALUE は書き込む生の
    YAML スカラー値をそのまま渡す（クォートが必要な場合は呼び出し側で含めること。
    例: --set 'removed_at="2026-07-29"'）。

--unset KEY
    frontmatter ブロック内の `KEY: ...` 行を削除する（複数指定可）。キーが存在しない
    場合は何もしない（冪等）。`--set` と同じく行単位の操作であり、複数行にまたがる
    値（ネストしたマッピング・リスト）は想定しない。値ではなく**キー名のみ**を渡す
    （`--set` / `--require` の KEY=VALUE 形式につられて `--unset KEY=VALUE` と
    書くと、黙って no-op になるのではなくエラーで止まる）。

    用途は「一度書かれた値を消す経路がどこにも無い」ことへの対処である（Issue #705）。
    例: 経路 B の再レビューが `review_status` を書き換える際、前回の経路 A で書かれた
    `reviewed_by` を同じ呼び出しで消す。

--require KEY=VALUE
    書き換えを実行する前に、frontmatter 内の現在の KEY の値が VALUE と一致するかを
    確認する（前後のクォート " / ' の有無は無視して比較する）。一致しなければ
    書き換えを行わず SKIP を報告して終了する（呼び出し元が「既に別の値になって
    いるので何もしない」を判断できるようにするための正常系であり、エラーでは
    ない）。省略した場合は無条件で適用する。`--set` と `--unset` の両方に一括して
    掛かる（1 回の呼び出しは 1 ページに対する 1 つの原子的な書き換えである、という
    既存の契約を変えない）。

Exit code:
    0 = 成功（実際に書き換えた場合、または --require 不一致で SKIP した場合）
    1 = <page> が存在しない / frontmatter ブロックが見つからない / 引数の形式が不正
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

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


def _remove_field(yaml_block: str, key: str) -> tuple[str, bool]:
    """yaml_block から `key: ...` 行を削除する。無ければ何もしない（冪等）。

    戻り値は (書き換え後のブロック, 実際に削除したか)。`_upsert_field` と同じく
    行単位の操作なので、行末の改行ごと落とす（CRLF も含む）。

    末尾の改行を落とすのは「削除した行が改行を持たない最終行だったとき」だけに
    限る。FRONTMATTER_RE の group(2) は通常「末尾に改行を含まない」ので、
    最終行を消すとその手前の改行が宙に浮き、呼び出し側が付け直す改行と合わさって
    frontmatter に空行が入る — そこだけを詰める。一方、frontmatter が空行で
    終わる場合は group(2) も改行で終わっており（`---\nk: v\n\n---\n` の
    group(2) は `k: v\n`）、これは元の書式として正当なので、中間行を消した
    ついでに無条件で rstrip すると、対象外の空行まで巻き添えに消えてしまう。
    """
    pattern = re.compile(rf"^{re.escape(key)}:[^\r\n]*(?:\r?\n|$)", re.MULTILINE)
    m = pattern.search(yaml_block)
    if m is None:
        return yaml_block, False
    removed = pattern.sub("", yaml_block, count=1)
    if not m.group(0).endswith("\n"):
        # 改行を持たない最終行だった。手前の行の改行が宙に浮くので1つだけ詰める。
        removed = re.sub(r"\r?\n\Z", "", removed)
    return removed, True


class FrontmatterFileError(Exception):
    """The page could not be opened, or holds no frontmatter block.

    Raised instead of printing-and-exiting so that in-process callers
    (`reset_review_on_content_change.py`, Issue #724) can report the failure
    in their own output vocabulary while `main()` keeps its existing CLI
    messages and exit code unchanged.
    """


class FieldWriteResult(NamedTuple):
    """Outcome of one apply_frontmatter_fields() call.

    `applied` is False only for the `require` mismatch — a normal outcome,
    not an error, which is why it is a return value rather than an
    exception. `current_value` carries what the field actually held, so the
    caller can say so in its own message.
    """

    applied: bool
    removed_keys: tuple[str, ...] = ()
    current_value: "str | None" = None


def apply_frontmatter_fields(
    page_path: Path,
    *,
    sets: "list[tuple[str, str]] | tuple[()]" = (),
    unsets: "list[str] | tuple[()]" = (),
    require: "tuple[str, str] | None" = None,
) -> FieldWriteResult:
    """Apply --set/--unset to one page's frontmatter block, in place.

    This is the whole of what the CLI does between argument parsing and
    printing, factored out so a second script can reuse it in-process
    (Issue #724). Keeping one implementation matters more here than usual:
    the delimiter handling below (re-adding the newline the frontmatter
    regex consumed when the closing `---` has none in front of it) is the
    kind of detail a copy silently gets wrong.
    """
    if not page_path.is_file():
        raise FrontmatterFileError(f"{page_path}: file does not exist")

    with page_path.open(encoding="utf-8-sig", newline="") as f:
        content = f.read()

    m = FRONTMATTER_RE.match(content)
    if not m:
        raise FrontmatterFileError(f"{page_path}: no frontmatter block found")

    yaml_block = m.group(2)
    delimiter = m.group(3)

    if require is not None:
        req_key, req_value = require
        current = _current_value(yaml_block, req_key)
        if current is None or current != _strip_quotes(req_value):
            return FieldWriteResult(applied=False, current_value=current)

    for key, value in sets:
        yaml_block = _upsert_field(yaml_block, key, value)

    removed_keys = []
    for key in unsets:
        yaml_block, removed = _remove_field(yaml_block, key)
        if removed:
            removed_keys.append(key)

    if not re.match(r"^\r?\n", delimiter):
        yaml_block += "\n"

    content = content[: m.start(2)] + yaml_block + content[m.end(2):]
    with page_path.open("w", encoding="utf-8", newline="") as f:
        f.write(content)

    return FieldWriteResult(applied=True, removed_keys=tuple(removed_keys))


def parse_kv(raw: str, flag: str) -> tuple[str, str] | None:
    """Parse a KEY=VALUE argument. Returns None (after printing an ERROR) on
    malformed input, so callers can propagate a normal `return 1` from
    main() instead of exiting mid-parse."""
    if "=" not in raw:
        print(f"ERROR: {flag} must be given as KEY=VALUE: {raw!r}", file=sys.stderr)
        return None
    key, _, value = raw.partition("=")
    key = key.strip()
    if not key:
        print(f"ERROR: the key of {flag} is empty: {raw!r}", file=sys.stderr)
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
        "--unset", dest="unsets", action="append", default=[], metavar="KEY",
        help="Field to remove if present (repeatable; no-op when absent)",
    )
    parser.add_argument(
        "--require", dest="require", default=None, metavar="KEY=VALUE",
        help="Only proceed if the field's current value matches; otherwise SKIP",
    )
    args = parser.parse_args()

    if not args.sets and not args.unsets:
        print("ERROR: give at least one --set or --unset", file=sys.stderr)
        return 1

    unset_keys = [raw.strip() for raw in args.unsets]
    if any(not key for key in unset_keys):
        print("ERROR: the key of --unset is empty", file=sys.stderr)
        return 1
    # --unset だけが KEY 単体を取り、`--set` / `--require` は KEY=VALUE を取る。
    # 兄弟フラグの書式につられて `--unset reviewed_by=""` と書いても、その文字列が
    # そのままキーとして扱われ、一致せず「無かった」として exit 0 で成功する —
    # 消したかった値が黙って残る。YAML のキーに現れない `=` / `:` を弾いて、
    # 書式違いを no-op ではなくエラーにする。
    for key in unset_keys:
        if "=" in key or ":" in key:
            print(
                f"ERROR: --unset takes a key name only, not KEY=VALUE: {key!r}",
                file=sys.stderr,
            )
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
    try:
        result = apply_frontmatter_fields(
            page_path, sets=set_pairs, unsets=unset_keys, require=require_pair
        )
    except FrontmatterFileError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not result.applied:
        req_key, req_value = require_pair
        print(
            f"SKIP: {args.page}: {req_key} is not {req_value!r} "
            f"(current: {result.current_value!r}); no changes made"
        )
        return 0

    removed_keys = result.removed_keys

    for key, value in set_pairs:
        print(f"OK: {args.page}: {key} -> {value}")
    for key in unset_keys:
        if key in removed_keys:
            print(f"OK: {args.page}: {key} removed")
        else:
            print(f"OK: {args.page}: {key} was not present; nothing to remove")
    print(f"SUMMARY: fields_set={len(set_pairs)}, fields_unset={len(removed_keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
