#!/usr/bin/env python3
"""reset_review_on_content_change.py — 内容が書き換わった `reviewed` ページを
`pending` へ戻す（Issue #724）。

信頼ラダーの上段（`review_status: reviewed` と、そこに添えられた `reviewed_by`
の実名）は「この文章を人間が読んだ」という主張である。ところが `reviewed` な
ページの本文を書き換える経路が 2 つあり、どちらもその主張を動かさないまま
文章だけを差し替えていた:

  - `wikicommit-generate` Pass 3 の `action: update`（既存の `reviewed` を
    明示的に維持する規則を持っていた）
  - `wikicommit-fix`（規則自体が無く、Edit してそのまま終わっていた）

後者の方が鋭い — `/wikicommit-fix` は「レビュー済みの内容が誤っていた」から
起動されるものであり、そのレビューが見落としたからこそ書き直された文章に、
レビュアーの実名が付き続けることになる。

ページを書き込む他の 4 経路（`action: create` / `--regenerate` /
`wikicommit-translate` / `wikicommit-synthesize`）はいずれも `pending` を書く。
本スクリプトは残る 2 経路を同じ原則に揃える。

## 判定は「常に戻す」ではなく「内容が変わったか」

無条件に戻すと、取り込みを続ける Wiki ではページが `reviewed` と `pending` を
往復し、そのたびにレビュー追跡 Issue が立つ — レビュー負荷が青天井になり
`reviewed` が到達不能になる。信頼ラダーの価値は上段に届くことにも依存している。

代わりに、`--regenerate` の unchanged-output valve と同じ形を採る: 書き出した
ページを、bookkeeping フィールドを除いて **HEAD の版と比較**し、異なるときだけ
戻す。同じ規則が入力の違いで別々に振る舞う — `action: update` では
bookkeeping だけの更新（ソース追記のみ等）が普通にあるため条件付きになり、
`wikicommit-fix` では定義上必ず内容が変わるため常に発火する。経路ごとに別の
規則は書かない。

## 内容と bookkeeping の線引き

無視するのは以下の 6 つだけで、**それ以外の frontmatter フィールドと本文は
すべて内容として扱う**（`--regenerate` の valve が 5 フィールドだけを無視する
のと同じ、ignore リスト方式）。判定は「人間のレビューが要るか否か」を左右する
ため、知らないフィールドは安全側＝内容として数える。

    generated_at / generated_by / generated_with / review_status /
    reviewed_by / sources

`sources` を bookkeeping 側に置くことが要である。`action: update` はほぼ必ず
ソースを追記する（それがこの分岐の目的である）ため、`sources` の変化を内容と
みなすと本スクリプトは「常に戻す」に潰れる。人間がレビューしたのは記述であり、
同じ記述に裏づけが 1 件増えることはその判断を無効にしない。

`expires_at` は内容側に残す — Pass 4 がこれを他の主張と同様にソースとの
照合対象にしている（Issue #279）以上、検証対象の主張である。

## なぜスクリプトか

完全に決定論的に判定できる操作を SKILL.md の散文として書くと、非決定論的な
失敗モードを持ち込む（Issue #474）。しかも本件は「人間のレビューが要るか否か」
を左右する判定であり、`--regenerate` の valve が同じ理由で比較を意味的同一性
ではなくテキスト一致にしているのと同じ配慮が要る。

Usage:
    python .wikicommit/scripts/reset_review_on_content_change.py <page>...

    <page> は `.wikicommit/entity/` または `.wikicommit/view/`（Issue #675）
    配下のページ。`wikicommit-fix` は両方のツリーを対象に取るため、entity
    ツリーだけを見るとその半分が黙って素通りする。`index.md` は
    `rebuild_index.py` がビルド生成物として `reviewed` を刻むページなので
    除外する（Issue #580）。

Exit code:
    0 = 正常終了（戻した／変わっていない／対象外、のいずれも正常系）
    1 = 引数が上記 2 ツリーの外を指している / ページが存在しない /
        作業ツリー側のページの frontmatter がパースできない
"""

import subprocess
import sys
from pathlib import Path

from _frontmatter import parse_frontmatter_and_body_text
from _wikilink import ENTITY_DIR, LEGACY_ENTITY_PREFIX, VIEW_DIR
from set_frontmatter_field import FrontmatterFileError, apply_frontmatter_fields

# 変わっても人間の再レビューを要求しないフィールド。ここに無いものはすべて内容。
# モジュール docstring の「線引き」節を参照。
BOOKKEEPING_FIELDS = frozenset(
    {
        "generated_at",
        "generated_by",
        "generated_with",
        "review_status",
        "reviewed_by",
        "sources",
    }
)

ACCEPTED_PREFIXES = (
    f"{ENTITY_DIR.as_posix()}/",
    f"{VIEW_DIR.as_posix()}/",
    # Issue #477 の .wikicommit/wiki/ -> entity/ 改名は自動移行しないため、
    # 旧ディレクトリのままのリポジトリからも呼ばれうる。
    LEGACY_ENTITY_PREFIX,
)


def _repo_relative(raw: str) -> str:
    """引数を git が理解するリポジトリ相対 POSIX パスに正規化する。

    `.wikicommit/scripts/` のスクリプトはリポジトリルートを cwd として実行される
    規約なので、絶対パスで渡された場合のみ cwd 基準へ落とす。
    """
    path = Path(raw)
    if path.is_absolute():
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _head_content(rel_path: str) -> str | None:
    """HEAD 時点のページ本文を返す。追跡されていなければ None。

    未追跡なら何もしない — 新規作成は元から `pending` であり、比較すべき
    前版が存在しない。

    **バイト列で受け取って作業ツリー側と同じ規則で自前でデコードする。**
    `text=True` に任せるとロケール依存のコーデックが使われ、`Path.read_text`
    が常に UTF-8 で読む作業ツリー側と非対称になる — 非 UTF-8 ロケール
    （Windows ネイティブ Python の cp932 / cp1252 等、Skills が対象に含める
    構成）では非 ASCII ページで `UnicodeDecodeError` が送出されて実行全体が
    途中で落ち、latin-1 系ロケールでは例外にならず文字化けした HEAD 版と
    突き合わせるため**全ページが無条件に降格する**。
    `utf-8-sig` で読むのも同じ対称性のためで、BOM 付きのページは
    `_split_frontmatter()` が `---` 始まりと認識できず frontmatter 無しに
    見えるため、BOM を落とさないと 1 文字も変えていないページが
    「内容が変わった」と判定される。改行コードの正規化は `text=True` の
    universal newlines と `Path.read_text` の既定の挙動に合わせる（CRLF の
    ページで frontmatter 側の値だけが食い違わないようにする）。
    """
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    text = result.stdout.decode("utf-8-sig", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_body(body: str) -> str:
    """本文比較用の正規化。改行コードと前後の空行の差だけで再レビューを
    要求しないための最小限に留める（内容の差を吸収しない）。"""
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def _content_fields(fm: dict) -> dict:
    return {k: v for k, v in fm.items() if k not in BOOKKEEPING_FIELDS}


def _changed_fields(head_fm: dict, work_fm: dict) -> list[str]:
    head_content = _content_fields(head_fm)
    work_content = _content_fields(work_fm)
    return sorted(
        key
        for key in set(head_content) | set(work_content)
        if head_content.get(key) != work_content.get(key)
    )


def process_page(raw_path: str) -> str:
    """1 ページを処理して結果種別（"reset" / "unchanged" / "skipped" / "error"）を返す。"""
    rel_path = _repo_relative(raw_path)

    if not rel_path.startswith(ACCEPTED_PREFIXES):
        print(
            f"ERROR: {raw_path}: specify a page under {ENTITY_DIR.as_posix()}/ "
            f"or {VIEW_DIR.as_posix()}/",
            file=sys.stderr,
        )
        return "error"

    page_path = Path(rel_path)
    if not page_path.is_file():
        print(f"ERROR: {raw_path}: file does not exist", file=sys.stderr)
        return "error"

    if page_path.name == "index.md":
        # `rebuild_index.py` がビルド生成のナビゲーションページとして書き出し、
        # まさにその理由で `review_status: reviewed` を刻む（Issue #580）—
        # 人間のレビューを経ていない `reviewed` はここだけが正当である。
        # 降格させると `wikicommit-merge` は index.md を追跡 Issue の対象外に
        # しているため Issue も立たず、公開サイトに未レビューバナーが出たまま
        # 誰も戻せない状態になる。他の全走査スクリプトと同じく除外する。
        print(f"SKIP: {raw_path}: index page (build-generated); nothing to demote")
        return "skipped"

    try:
        work_text = page_path.read_text(encoding="utf-8-sig")
    except OSError as e:
        print(f"ERROR: {raw_path}: could not be read: {e}", file=sys.stderr)
        return "error"

    work_fm, err, work_body = parse_frontmatter_and_body_text(work_text)
    if err:
        print(f"ERROR: {raw_path}: {err}", file=sys.stderr)
        return "error"

    if str(work_fm.get("review_status", "")) != "reviewed":
        print(f"SKIP: {raw_path}: review_status is not reviewed; nothing to demote")
        return "skipped"

    head_text = _head_content(rel_path)
    if head_text is None:
        print(f"SKIP: {raw_path}: not tracked at HEAD; no earlier version to compare")
        return "skipped"

    head_fm, head_err, head_body = parse_frontmatter_and_body_text(head_text)
    if head_err:
        # HEAD 側が読めないときは安全側（内容が変わったものとして扱う）に倒す。
        # 誤って戻す代償は追跡 Issue が 1 件増えることだが、誤って維持する
        # 代償は人間が読んでいない文章に署名が残ることである。
        print(
            f"WARNING: {raw_path}: the HEAD frontmatter could not be read "
            f"({head_err}); treating the content as changed",
            file=sys.stderr,
        )
        changed = ["(HEAD unparsable)"]
    else:
        changed = _changed_fields(head_fm, work_fm)
        if _normalize_body(head_body) != _normalize_body(work_body):
            changed.append("body")

    if not changed:
        print(f"UNCHANGED: {raw_path}: content matches HEAD; review_status kept as reviewed")
        return "unchanged"

    try:
        apply_frontmatter_fields(
            page_path,
            sets=[("review_status", "pending")],
            unsets=["reviewed_by"],
        )
    except FrontmatterFileError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return "error"

    print(
        f"RESET: {raw_path}: content changed since HEAD ({', '.join(changed)});"
        f" review_status reviewed -> pending, reviewed_by dropped"
    )
    return "reset"


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "ERROR: specify at least one page: "
            "reset_review_on_content_change.py <page>...",
            file=sys.stderr,
        )
        return 1

    counts = {"reset": 0, "unchanged": 0, "skipped": 0, "error": 0}
    for raw_path in argv:
        counts[process_page(raw_path)] += 1

    print(
        f"SUMMARY: reset={counts['reset']}, unchanged={counts['unchanged']},"
        f" skipped={counts['skipped']}, errors={counts['error']}"
    )
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
