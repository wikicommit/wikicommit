#!/usr/bin/env python3
"""
resolve_source_cache_path.py — wikicommit-ask の `--include-source`（Issue #470）
バックエンドスクリプト。

ソースの識別子（`sources[].url` または `sources[].path`）から、対応する抽出テキスト
キャッシュの実在パスを特定する。

**同一性キーは常に管理ファイルの `source.url` / `source.path` であり、識別子から
ファイル名を再計算しない。** `wikicommit-generate` のキャッシュ置き場は「ソース管理
ファイルの実際の相対パス」から導出されるのであって、識別子から `url_to_filename()` /
`mgmt_path_for_file()` で再計算した名前ではない。再計算すると、Issue #191（旧フラット
命名）・#192（旧パーセントエンコード命名）・#572（クエリを落としていた命名）・#573
（拡張子を置き換えていた命名）より前に登録された管理ファイル（いずれも自動移行されない）
で実際のパスと食い違い、実在するキャッシュを「見つからない」と誤判定する。
`add_source.py` の `find_mgmt_file_for_url()` / `find_mgmt_file_for_path()` が登録側で
採っているのと同じ実走査による同一性判定である（Issue #572 / #573）。

## 2 つのソース種別でキャッシュの木が違う

| `--type` | 走査する管理ファイル | キャッシュの木 | 書く主体 |
|---|---|---|---|
| `url`    | `.wikicommit/source/url/`  | `.wikicommit/.cache/ingest-fetch/`  | Pass 1 のフェッチ |
| `path`   | `.wikicommit/source/path/` | `.wikicommit/.cache/extract-path/` | Pass 1 の抽出（Issue #885） |

導出規則も対称ではない。`url` 側は管理ファイルの相対パスから拡張子を落として `.md` を
付け直す（旧来の scratch-path の定義）一方、`path` 側は**末尾の `.md` を落とさずそのまま
使う** — 管理ファイル名が元の拡張子を保持する形（`raw/paper.pdf.md`。Issue #573）なので、
そのまま使えば `paper.pdf` と `paper.docx` が同じキャッシュへ解決する衝突が構造的に
起こらない。`add_source.py` の `extract_cache_path()` と同じ規則である。

Usage:
    echo "<url>"  | python resolve_source_cache_path.py --type url
    echo "<path>" | python resolve_source_cache_path.py --type path

識別子は stdin から読む（argv ではない — `sources[].url` / `sources[].path` は
`validate_frontmatter.py` が形式を検証するだけで、シェル引数として安全であることは
一度も確かめられていない。Issue #375）。`--type` は呼び出し側が
書く固定のリテラルなのでこの規則の対象外。

一致する管理ファイルが見つかり、**かつ**キャッシュファイルがディスク上に実在する場合に
そのパス（リポジトリルート相対）を stdout に印字する。

## exit 1 の 2 つの意味を印字で分ける（Issue #1036）

exit 1 は「一致する管理ファイルが無い」と「キャッシュが無い」の 2 つを畳んでいる。
終了コードは変えず（`wikicommit-review` / `wikicommit-fix` / `wikicommit-relate` は
exit 1 をどちらでも同じフォールバックで答える）、stdout の 1 行で区別する:

    UNREGISTERED: <識別子>
    NO_CACHE: <キャッシュが置かれるはずの位置> (<管理ファイル>)

`wikicommit-ask --include-source` は後者で URL を取得し、前者ではキャッシュに置けない
（置き場所が管理ファイルのパスから導かれる）ことをこの行から知る。

`--type path` では、識別子の解決先（`resolve()` 後）がリポジトリルートの配下に無ければ
どちらの行でもなく次を印字する（exit 1 のまま。Issue #1206）:

    OUTSIDE: <識別子>

`wikicommit-ask --include-source` は `type: path` の `UNREGISTERED:` / `NO_CACHE:` に
生ファイルを直接読むことで答えるので、絶対パス・`..`・外を指すシンボリックリンクが
その 2 行に落ちるとリポジトリ外のファイルがコンテキストに入る。`OUTSIDE:` を受けた
呼び出し側はそのパスを開かない。判定は `--obtain` と同じ `_inside()` で、管理ファイルの
照会結果（`UNREGISTERED` / `NO_CACHE`）より前に置く（`--obtain` が `missing` より前に
置くのと同じ理由 — 後に置くと外のパスについて何かが分かる）。取り下げ（exit 2）だけは
その前に見る（`--obtain` と同じ順序）。

## `--settle` — キャッシュが無かった URL を取得した後の判定（Issue #1036）

呼び出し元は `wikicommit-ask --include-source` と、`wikicommit-review` / `wikicommit-fix`
（`.wikicommit/.cache/refetch/` に取得した後。Issue #1137）。

clean checkout ではキャッシュが常に空なので、`--include-source` は URL ソースを毎回
諦めていた。ask は `add_source.py --fetch-url` で一時ファイルに取得し、本モードに渡す。
取得した内容のハッシュを**2 つの値と別々に**照合する:

| 照合の相手 | 答える問い |
|---|---|
| ページの `sources[].hash`（`--page-hash`） | ページが書かれたときの版か（＝抽出ガードを通った版か） |
| 管理ファイルの `source.hash` | generate が今キャッシュとして期待している版か |

**後者が一致したときだけ**キャッシュの位置へ移す。2 つは一致するとは限らない（保留した
`LOW_DENSITY:` の取得、破棄された強制リチェックは管理ファイルの hash だけを進める）。
管理ファイルには一切書き込まず、置かなかった一時ファイルも消さない（呼び出し側が読んで
から消す）。出力は 1 行:

    SETTLED: page=<match|mismatch>, cache=<placed <path>|not-placed (<理由>)>, read=<読むファイル>

取り下げ済みなら `RETRACTED:` と exit 2（取得前の照会で既に分かるはずだが、
置く前にもう一度見る）。

## `--obtain` — 1 エントリぶんの本文を得る（Issue #1190）

呼び出し元は下の `--obtain-sources`（エントリごとにこれを 1 回）。以前は
キャッシュ照会・`type: path` キャッシュの版の照合・`add_source.py --fetch-url`・`--settle`・
scratch の扱いを散文で順に指示していたが、どれも決定論的なので 1 コマンドに寄せた。
エージェントに残る判断は「抽出 Skill を呼ぶ」だけである。出力は 1 行:

    READ: <読むファイル> page=<match|mismatch>   （exit 0）
    EXTRACT: <path>                               （exit 0。抽出 Skill が要る）
    RETRACTED: <識別子> (<管理ファイル>)         （exit 2）
    UNAVAILABLE: <environment|fetch|missing|outside> (<理由>)   （exit 1）

- 取り下げ（`status: retracted`）は何かを読む・取得する前に見る
- `type: path` の解決先（シンボリックリンクを辿った `resolve()` 後のパス）がリポジトリ
  ルートの配下に無ければ `UNAVAILABLE: outside`（Issue #1201）。絶対パス・`..` で外へ
  出るパス・外を指すシンボリックリンクがこれに当たる（中を指すシンボリックリンクは
  正当なソースとして読む）。存在の判定（`missing`）より前に置く — 後に置くと、
  リポジトリ外のパスが存在するかどうかが `missing` か否かで分かってしまう
- `type: path` の `.md` / `.txt` は生ファイルを読む（キャッシュを持たない）。拡張子は
  シンボリックリンクを辿った解決先のもので判定し、`READ:` / `EXTRACT:` が返すパスも解決先
  にする（Issue #1208。`.md` 名のリンクが PDF を指すとき、リンク名で判定すると PDF の
  バイナリを `READ:` で返し、リンク名を返すと抽出 Skill の選択〈拡張子で引く〉を誤る）。
  generate の Pass 1 も `add_source.py --check-path-cache` の `RAW:` / `extract=` で同じ
  解決先を見るので、生成と照合は同じテキストを使う（Issue #1216）。それ以外は
  抽出キャッシュがあり、**かつ生ファイルの現在のハッシュが管理ファイルの `source.hash`
  と一致するときだけ**キャッシュを読む（キャッシュはその版の抽出結果。
  `add_source.py --check-path-cache` と同じ判定）。そうでなければ `EXTRACT:`。
  キャッシュの位置はリンク名でも解決先でもなく**管理ファイル**から決まり（generate が書く
  位置と同じ）、`.md` 名のリンクが PDF を指す場合も generate が書いた抽出結果に当たる
- `type: url` はキャッシュがあれば読み、無ければ `add_source.py --fetch-url` で
  `.wikicommit/.cache/refetch/<label>-<index>.md` に取得し（同名の古いファイルは先に消す）、
  `--settle` と同じ判定で置く。exit 3 は `UNAVAILABLE: environment`（ネットワークが無い —
  ソースではなく環境の問題）、それ以外の失敗は `UNAVAILABLE: fetch`
- `page=` は読むファイル（`type: path` では生ファイル）が `--page-hash` と一致するか
- 管理ファイルには書き込まない。置かれなかった scratch ファイルは呼び出し側が消す

`wikicommit-ask --include-source` はこのモードに乗せていない — 取得前の
`check-fetch-capability`、`NETWORK_UNAVAILABLE` 後に残りを取得しない挙動、`ask-fetch/` の
通し番号、`type: path` で抽出 Skill を呼ばず生ファイルを読む挙動が ask 固有であるため。

## `--obtain-sources` — ページの `sources` 全件の本文を得る（Issue #1211）

呼び出し元は `wikicommit-review` Step 4 / `wikicommit-fix` Step 3。stdin に**どのページの
`sources` を使うか**（翻訳ページなら親ページ）のパスを渡す — その選択は呼び出し側の Skill が
決め、このスクリプトには持ち込まない。全エントリについて `--obtain` と同じ処理を順に行い、
エントリごとに 1 行、最後に `SUMMARY:` を印字する:

    READ: [<n>] <読むファイル> page=<match|mismatch>
    EXTRACT: [<n>] <path>                      （抽出 Skill を呼ぶのはエージェント）
    RETRACTED: [<n>] <識別子> (<管理ファイル>)
    UNAVAILABLE: [<n>] <environment|fetch|missing|outside|invalid> <識別子> (<理由>)
    MANUAL: [<n>]                              （`type: manual`。ソース文書が無い）
    SUMMARY: entries=<N> read=… extract=… retracted=… unavailable=… manual=…
    CONTINUE: next=<n>                         （時間の区切りで止めた。`--from <n>` で呼び直す）

`<n>` は `sources` 内の位置（1 始まり）。`READ:` / `EXTRACT:` のパスがシンボリックリンクの
解決先やキャッシュであって `sources[].path` と一致しなくても、どのエントリかは `<n>` で
分かるので、元の識別子は併記しない（Issue #1216）。**行のキーワードがそのまま呼び出し側の次の行動に
対応する**（行に指示文は埋め込まない）。取り下げ済みのエントリは何も読まず・取得せずに
`RETRACTED:` になるので、以前 review / fix が取得の前に走らせていた
`check_retracted_sources.py --list` の照合はこのコマンドに含まれる。終了コードは
`check_retracted_sources.py --list` と同じく一覧なので 0（取り下げ・取得失敗は行で伝える）。
exit 1 はページがリポジトリ外・読めない・frontmatter が壊れている・`--label` の誤り。

**取得には時間の区切りがある**（Issue #1240）。1 件の取得は `add_source.py` のタイムアウト
（接続 15 秒・読み取り 60 秒）で止まるが、件数ぶん積み重なるとエージェントのシェルの制限時間
（Claude Code の Bash は既定 120 秒）を超え、途中で切られる。`--budget <秒>`（既定 45。
`check_external_links.py` と同じ）を過ぎたら新しい取得を始めず、まだのエントリの行は出さずに
`SUMMARY:` の後へ `CONTINUE: next=<n>` を印字する。呼び出し側は `--from <n>` で同じコマンドを
呼び直し、`CONTINUE:` が出なくなるまで続ける。その回の最初の取得は区切りに関係なく始める
（呼び直しのたびに少なくとも 1 件進む）。区切りが掛かるのは取得だけで、キャッシュのある URL・
`type: path`・`manual` は区切りの後でも、次に取得の要るエントリに当たるまでは出す — どれも
待たない（そこから後は取得が要るかどうかにかかわらず次の呼び出しで出る）。`SUMMARY:` はその回に
出した行だけを数える。

**ネットワーク不在が 2 回続いたら、残りは取得しない。** 取得が exit 3（接続段階の失敗）で
2 回続いたら、その回の残りのキャッシュの無い URL エントリは `add_source.py` を呼ばずに
`UNAVAILABLE: [<n>] environment … (not fetched: …)` にする。1 回で止めないのは、消えたドメイン
1 件の名前解決の失敗がネットワーク不在と同じ形になるためで、しきい値は generate の Pass 2c と
同じ。取得の成功と `fetch` の失敗で数え直す。数えるのは 1 回の呼び出しの中だけ。

**並列には取得しない。** シェルの制限時間の問題は上の区切りで解け、並列にすると行の `[<n>]` 順・
途中で切られたときにそれまでの行が残る性質・同じ URL が `sources` に 2 度あるときの
`settle_fetch()` の競合に手当てが要る。1 ページの URL ソースはふつう数件である。

始める前に `.wikicommit/.cache/refetch/<label>-*.md` を消す（`--from <n>` のときは
`<label>-<m>.md` のうち `m >= n` の分だけ — それより前は前の呼び出しの `READ:` が指している
ファイルでありうる）。scratch は書いた実行の中でしか
読まれないので、残っているのは前の実行のものである。読み終えたことはスクリプトから
分からないため、実行の最後の後始末（`rm -f`）は呼び出し側に残る — 残しても次の実行が最初に
消すので、溜まるのは 1 実行ぶんまでである。

## 取り下げ済みソース（`status: retracted`）は exit 2 で伝える（Issue #918）

管理ファイルの `status` が `retracted` なら、キャッシュの有無を見る前に `RETRACTED:` 行を
stdout に印字して exit 2 を返す。**これは人間が「このソースの内容は信用できない」と判断した
印**であり（Issue #737）、取り込み側では再登録も `outdated` への復帰も構造的に止まるのに、
参照側（`--include-source`）にはガードが 1 つも無かった。機械はソースを疑えない（証拠拘束
ルール。Issue #442）ので、この値は人間にしか書けず、読む主体が居なければ何も起きない。

**exit 1 に畳めない。** あちらは既に 2 つの意味（一致する管理ファイルが無い／キャッシュが
実在しない）を畳んでおり、しかも呼び出し側は `type: path` の exit 1 で**生ファイルを直接
読むフォールバック**へ進む — 取り下げ済みソースがキャッシュを持たない場合、exit 1 を返すと
そのまま素通りする。`status` はキャッシュの有無と独立なので、両方の経路に効く必要がある。

**`retracted` 以外の `status` は見ない。** `failed` / `excluded` / `partial` / `outdated` は
いずれも取り込み処理の状態であって、そのソースの**内容**に対する評価ではない。読む価値が
あるのは `retracted` だけで、他を足すと `status` 全体を解釈する分岐が参照側にもう 1 つ
生まれる（Issue #553 の「消費者と同時に足す」）。

**frontmatter が壊れている管理ファイルは、黙って飛ばさず stderr に `WARNING:` を出す。**
`status: retracted` は人間が手で書く値であり、管理ファイルを検証するものは 1 つも無いので、
取り下げを書き込むときの打ち間違いがそのままこのガードを黙って無効化しうる — 一致する
管理ファイルが無い場合と区別が付かなくなり、`type: path` の経路では生ファイルが読まれる。
`check_extraction_quality.py` が `source-policy.md` のパース失敗で無言の fail-open を
避けているのと同じ理由（stdout の契約は変えない）。

Exit codes:
    0 — キャッシュが見つかり印字した（`--settle` では判定を印字した。`--obtain` では
        `READ:` / `EXTRACT:`）
    1 — 一致する管理ファイルが無い（`UNREGISTERED:`）、キャッシュファイルが
        実在しない（`NO_CACHE:`）、または `--type path` の解決先がリポジトリ外
        （`OUTSIDE:`。生ファイルを読まない）。`--settle` では引数の誤り・取得ファイルが無い。
        `--obtain` では `UNAVAILABLE:`・引数の誤り。`--obtain-sources` では引数の誤り・
        ページが読めない（それ以外は 0）
    2 — 管理ファイルが `status: retracted` である
        （`RETRACTED: <識別子> (<管理ファイルのパス>)` を印字。後者は
        人間が書いた `## Retraction Reason` の在り処である）
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _frontmatter import parse_frontmatter  # noqa: E402
from _wikilink import resolve_stored_entity_path  # noqa: E402


class Retracted:
    """Returned in place of a cache path when the management file is retracted.

    Deliberately not a `Path`: a caller must not be able to read it as somewhere
    to look. Deliberately not `None` either — that value already carries two
    meanings here (no matching management file, no cache on disk) and a caller
    acting on it reads the raw file instead, which is exactly what must not
    happen for a source a person withdrew.

    Carries the management file so the caller can point at the
    `## Retraction Reason` a person wrote there (Issue #737), which is the only
    place the *why* exists.
    """

    def __init__(self, management_file: Path) -> None:
        self.management_file = management_file


def _is_retracted(fm: dict) -> bool:
    return str(fm.get("status") or "").strip() == "retracted"


def _frontmatter_or_none(management_file: Path) -> dict | None:
    """Parse a management file's frontmatter, warning rather than failing open.

    `parse_frontmatter` answers unparseable YAML with `(None, error)`, and a
    silent `continue` on that would switch the retraction guard off for exactly
    the files most likely to carry one: `status: retracted` is written by hand
    (Issue #737) and nothing validates a source management file, so a typo made
    while writing the retraction leaves the source looking unregistered — which
    is the ordinary miss, and on the `type: path` route the caller answers a
    miss by reading the raw file. Same reason `check_extraction_quality.py`
    warns instead of failing open when `source-policy.md` will not parse.

    A file with no frontmatter block at all is not an error and is skipped
    quietly, the way it always was.
    """
    fm, err = parse_frontmatter(management_file)
    if fm is None:
        print(
            f"WARNING: {management_file}: {err}; skipped, so a `status: retracted` "
            "written there would not be seen",
            file=sys.stderr,
        )
        return None
    return fm or None


class Located:
    """What the scan of one tree found for an identifier.

    `management_file` is None when nothing is registered for the identifier.
    `cache_file` is where the cache *belongs* — it may not exist. Keeping the two
    apart is what lets the CLI tell an unregistered source from a missing cache
    (Issue #1036), which exit 1 alone folds together.
    """

    def __init__(
        self,
        management_file: Path | None = None,
        cache_file: Path | None = None,
        frontmatter: dict | None = None,
        retracted: bool = False,
    ) -> None:
        self.management_file = management_file
        self.cache_file = cache_file
        self.frontmatter = frontmatter or {}
        self.retracted = retracted


def _same_identifier(recorded, target: str) -> bool:
    """Whether a management file's `source.url` / `source.path` names `target`.

    The recorded value is read from the file as UTF-8, while an identifier read
    from stdin is decoded the way the OS decodes file names (`use_utf8_streams()`).
    Under a locale that is not UTF-8 those are two spellings of the same bytes —
    surrogates under a POSIX `C` locale — so a registered non-ASCII source would
    otherwise come back UNREGISTERED, and on the `path` route the caller then
    reads the raw file past a `status: retracted` (Issue #1265).
    """
    if not isinstance(recorded, str):
        return False
    if recorded == target:
        return True
    try:
        return os.fsdecode(recorded.encode("utf-8", "surrogateescape")) == target
    except (UnicodeError, ValueError):
        return False


def _locate(
    target: str, key: str, mgmt_root: Path, cache_for
) -> Located:
    if not mgmt_root.is_dir():
        return Located()
    for management_file in mgmt_root.rglob("*.md"):
        fm = _frontmatter_or_none(management_file)
        if fm is None:
            continue
        source = fm.get("source")
        if not isinstance(source, dict) or not _same_identifier(source.get(key), target):
            continue
        # Read before the cache lookup, not after: a retracted source with no
        # cache would otherwise come back as an ordinary miss.
        return Located(
            management_file=management_file,
            cache_file=cache_for(management_file),
            frontmatter=fm,
            retracted=_is_retracted(fm),
        )
    return Located()


def locate_url(target_url: str, repo_root: Path = Path()) -> Located:
    mgmt_root = repo_root / ".wikicommit" / "source" / "url"

    def cache_for(management_file: Path) -> Path:
        scratch_path = management_file.relative_to(mgmt_root).with_suffix("")
        return (repo_root / ".wikicommit" / ".cache" / "ingest-fetch" / scratch_path).with_suffix(".md")

    return _locate(target_url, "url", mgmt_root, cache_for)


def locate_path(target_path: str, repo_root: Path = Path()) -> Located:
    """比較は `source.path` の文字列そのものに対して行う。`add_source.py` の
    `find_mgmt_file_for_path()` と同じで、パスの正規化（`./` の除去・`resolve()`）は
    しない — あちらが登録時に書いた値と、ページの `sources[].path` に転記された値は
    同じ 1 つの文字列であり、その間に正規化を挟む主体がいない。
    """
    mgmt_root = repo_root / ".wikicommit" / "source" / "path"

    def cache_for(management_file: Path) -> Path:
        # 末尾の `.md` を落とさない（上の docstring 参照）。
        rel = management_file.relative_to(mgmt_root)
        return repo_root / ".wikicommit" / ".cache" / "extract-path" / rel

    return _locate(target_path, "path", mgmt_root, cache_for)


def _resolved(located: Located) -> Path | Retracted | None:
    if located.management_file is None:
        return None
    if located.retracted:
        return Retracted(located.management_file)
    return located.cache_file if located.cache_file.is_file() else None


def resolve_url(target_url: str, repo_root: Path = Path()) -> Path | Retracted | None:
    """The cache path, a `Retracted`, or None. See the module docstring."""
    return _resolved(locate_url(target_url, repo_root))


def resolve_path(target_path: str, repo_root: Path = Path()) -> Path | Retracted | None:
    """`type: path` のソースの抽出テキストキャッシュを解決する（Issue #885）。

    取り下げ済みの場合は `Retracted` を返す（Issue #918）。ここで返さないと、
    キャッシュを持たない取り下げ済みソースが `None`（＝生ファイルを読むフォールバック）
    に落ちて素通りする。
    """
    return _resolved(locate_path(target_path, repo_root))


def sha256_file(path: Path) -> str:
    """Same digest `add_source.py` writes into `source.hash` and `sources[].hash`."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _recorded_hash(located: Located) -> str:
    """The management file's `source.hash`, or "" when it is not set."""
    source = located.frontmatter.get("source") or {}
    return str(source.get("hash") or "").strip().strip('"')


def _page(got: str, page_hash: str) -> str:
    """Whether a digest is the version the page's `sources[].hash` records."""
    return "match" if page_hash and got == page_hash.strip() else "mismatch"


def settle_fetch(
    target_url: str, fetched: Path, page_hash: str, repo_root: Path = Path()
) -> dict:
    """Decide what a fresh `--include-source` fetch may be used for (Issue #1036).

    Two comparisons, answering two different questions:

    - against the grounding page's own `sources[].hash` — is this the version the
      page was written from? Only then did the text pass the extraction guards
      Pass 1 applied when the page was made, so only then is it used without a
      note.
    - against the management file's `source.hash` — is this the version
      `wikicommit-generate` now expects in its cache? Only then is it moved into
      the cache. Pass 1 always checks that hash before reading the cache, so a
      file placed here can never mislead generate; the reason not to place
      anything else is the *next* ask, which would read a different version as
      "the cached source" with no note at all.

    The two can disagree: a deferred `LOW_DENSITY:` fetch, or a forced recheck
    whose update was discarded, moves `source.hash` without the page following.

    Never writes to the management file. Never deletes: a file that is not
    placed stays where it was fetched, for the caller to read and then remove.
    """
    located = locate_url(target_url, repo_root)
    if located.retracted:
        return {"result": "RETRACTED", "management_file": located.management_file}

    if not fetched.is_file():
        return {"result": "ERROR", "message": f"{fetched}: the fetched file does not exist"}

    got = sha256_file(fetched)

    if located.management_file is None:
        cache = "not-placed (no management file is registered for this URL)"
        read = fetched
    else:
        recorded = _recorded_hash(located)
        if not recorded:
            cache = "not-placed (the management file's source.hash is not set)"
            read = fetched
        elif got != recorded:
            cache = "not-placed (differs from the management file's source.hash)"
            read = fetched
        else:
            target = located.cache_file
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(fetched, target)
            cache = f"placed {_rel(target, repo_root)}"
            read = target

    return {
        "result": "SETTLED",
        "page": _page(got, page_hash),
        "cache": cache,
        "read": read,
        "hash": got,
    }


# ── --obtain (Issue #1190) ────────────────────────────────────────────────────

# Read raw, never cached: the file is already the extracted text. The same set
# as `add_source.py`'s `RAW_TEXT_SUFFIXES`, which `--check-path-cache` applies
# for generate's Pass 1 to the same resolved target (Issue #1216); a test keeps
# the two in step, since the scripts do not import each other.
_RAW_SUFFIXES = {".md", ".txt"}
# The fetcher, next to this script in `.wikicommit/scripts/` (Issue #1210).
ADD_SOURCE = Path(__file__).resolve().parent / "add_source.py"
_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def run_fetch(url: str, output: Path, repo_root: Path) -> tuple[int, str]:
    """Fetch `url` into `output` with `add_source.py --fetch-url`.

    A subprocess, not an import: `add_source.py` is self-contained and keeps its
    fetcher (User-Agent, markitdown session, connection-failure detection) to
    itself. The URL travels in argv of an exec, never through a shell.
    Returns (exit code, one line of what it printed). Only the last non-empty
    line is kept: a crash (a missing `markitdown`, say) prints a traceback, and
    the caller's contract is one output line.
    """
    if not ADD_SOURCE.is_file():
        return 1, f"{ADD_SOURCE} not found"
    # UTF-8 both ways whatever the locale (Issue #1256): the line handed back can
    # carry a non-ASCII path or URL, which a cp1252 child could not print and a
    # cp932 parent would misread.
    try:
        proc = subprocess.run(
            [sys.executable, str(ADD_SOURCE), "--fetch-url", url, "--output", str(output)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=repo_root, check=False,
        )
    except UnicodeEncodeError as err:
        # A URL from a page's `sources` (`--obtain-sources`) is UTF-8 text, and
        # under a locale that is not UTF-8 argv cannot carry it. One line, not a
        # traceback: the caller's contract is one line per entry (Issue #1265).
        return 1, f"cannot pass the URL to add_source.py under this locale ({err.reason}); set PYTHONUTF8=1"
    lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    lines = lines or [line.strip() for line in proc.stderr.splitlines() if line.strip()]
    return proc.returncode, (lines[-1] if lines else f"exit {proc.returncode}")


def _inside(path: Path, repo_root: Path) -> bool:
    """Whether `path`, symlinks followed, lies under `repo_root`.

    An absolute identifier makes `repo_root / identifier` the identifier itself,
    and `..` climbs out; both are caught here because the check is on the
    resolved path rather than on the string. A symlink inside the repository
    is a legitimate source only while its target is inside the repository too.
    """
    return _target_inside(path, repo_root) is not None


def _target_inside(path: Path, repo_root: Path) -> Path | None:
    """`path`'s target, symlinks followed, relative to `repo_root`; None if outside.

    One resolution serves both the containment check and the target that
    `--obtain` reads (Issue #1208), so a link swapped between the two cannot
    hand back a path that was never checked.
    """
    try:
        resolved = path.resolve()
        root = repo_root.resolve()
    except (OSError, RuntimeError, ValueError):
        # ValueError: an embedded NUL byte. Fail closed rather than crash
        # without printing OUTSIDE / UNAVAILABLE.
        return None
    return resolved.relative_to(root) if resolved.is_relative_to(root) else None


def obtain(
    source_type: str,
    identifier: str,
    label: str,
    index: int,
    page_hash: str,
    repo_root: Path = Path(),
    fetch=run_fetch,
) -> dict:
    """Everything deterministic about getting one `sources[]` entry's text.

    Results: READ (file, page), EXTRACT (path), RETRACTED (management_file),
    UNAVAILABLE (reason, message). See the module docstring.
    """
    if source_type == "path":
        located = locate_path(identifier, repo_root)
        if located.retracted:
            return {"result": "RETRACTED", "management_file": located.management_file}
        raw = repo_root / identifier
        # Before the existence check: otherwise `missing` would tell whether a
        # file outside the repository exists. On the resolved path, so a
        # symlink in the repository that points outside is refused too.
        target = _target_inside(raw, repo_root)
        if target is None:
            return {
                "result": "UNAVAILABLE",
                "reason": "outside",
                "message": f"{identifier} resolves outside the repository",
            }
        # The file the bytes come from, symlinks followed (Issue #1208): a
        # `notes.md` link to `scan.pdf` is a PDF, and the extraction skill is
        # chosen by extension, so both the READ/EXTRACT split and the path
        # handed back use the target, not the link's own name.
        raw = repo_root / target
        if not raw.is_file():
            return {"result": "UNAVAILABLE", "reason": "missing", "message": f"{identifier} does not exist"}
        if raw.suffix.lower() in _RAW_SUFFIXES:
            return {"result": "READ", "file": raw, "page": _page(sha256_file(raw), page_hash)}
        recorded = _recorded_hash(located) if located.management_file else ""
        if located.cache_file is not None and located.cache_file.is_file() and recorded:
            current = sha256_file(raw)
            if current == recorded:
                return {"result": "READ", "file": located.cache_file, "page": _page(current, page_hash)}
        return {"result": "EXTRACT", "file": raw}

    located = locate_url(identifier, repo_root)
    if located.retracted:
        return {"result": "RETRACTED", "management_file": located.management_file}
    if located.cache_file is not None and located.cache_file.is_file():
        return {
            "result": "READ",
            "file": located.cache_file,
            "page": _page(sha256_file(located.cache_file), page_hash),
        }

    scratch = repo_root / ".wikicommit" / ".cache" / "refetch" / f"{label}-{index}.md"
    # A file an earlier run left under this name is not this fetch's result.
    scratch.unlink(missing_ok=True)
    code, message = fetch(identifier, scratch, repo_root)
    if code != 0 or not scratch.is_file():
        scratch.unlink(missing_ok=True)
        reason = "environment" if code == 3 else "fetch"
        return {"result": "UNAVAILABLE", "reason": reason, "message": message}

    settled = settle_fetch(identifier, scratch, page_hash, repo_root)
    if settled["result"] == "RETRACTED":
        scratch.unlink(missing_ok=True)
        return settled
    return {"result": "READ", "file": settled["read"], "page": settled["page"]}


# ── --obtain-sources (Issue #1211) ────────────────────────────────────────────


def obtain_sources(
    page: Path, label: str, repo_root: Path = Path(), fetch=run_fetch, **kwargs
) -> list[dict]:
    """`obtain()` for every entry of `page`'s `sources`, in order.

    Which page's `sources` applies (a translation's parent, say) is the
    caller's decision; this reads the list of the page it is given. Each result
    carries `index` (1-based) and `identifier`; a `type: manual` entry is
    MANUAL, an entry with no usable identifier is UNAVAILABLE (invalid).
    `kwargs` (`start`, `budget`, `clock`) go to `iter_obtain_sources()`; with a
    `budget`, the last result may be CONTINUE (see there).
    """
    fm, _ = parse_frontmatter(page)
    return list(iter_obtain_sources((fm or {}).get("sources"), label, repo_root, fetch, **kwargs))


# Consecutive environment failures (exit 3) after which the rest of a call's
# fetches are not attempted: the same threshold as generate's Pass 2c, so one
# vanished domain (a DNS failure looks like no network) does not stop the rest.
ENVIRONMENT_STREAK = 2


class _OutOfBudget(Exception):
    """Raised by the budgeted fetcher instead of starting a fetch past the budget."""


def _budgeted(fetch, budget: float | None, clock):
    """Wrap `fetch` with the time budget and the environment-failure streak.

    Only real fetches count: `obtain()` calls the fetcher only for a URL entry
    with no cache, so a cached URL, a `type: path` or a `manual` entry is
    answered past the budget too, up to the first entry that needs a fetch
    (everything from there on goes to the next call). The first fetch of a call always starts, so
    every call makes progress.
    """
    started = clock()
    state = {"fetched": 0, "streak": [], "index": ""}

    def wrapped(url: str, output: Path, repo_root: Path) -> tuple[int, str]:
        if len(state["streak"]) >= ENVIRONMENT_STREAK:
            where = " and ".join(state["streak"])
            return 3, f"not fetched: the network was unavailable for {where}"
        if budget is not None and state["fetched"] and clock() - started >= budget:
            raise _OutOfBudget
        state["fetched"] += 1
        code, message = fetch(url, output, repo_root)
        if code == 3:
            state["streak"].append(state["index"])
        else:
            state["streak"] = []
        return code, message

    return wrapped, state


def iter_obtain_sources(
    entries, label: str, repo_root: Path = Path(), fetch=run_fetch,
    *, start: int = 1, budget: float | None = None, clock=time.monotonic,
):
    """Yield `obtain_sources()`'s results one entry at a time.

    A generator so that `main()` prints each line as soon as it is known: a
    crash or an interrupt partway through a run of slow fetches still leaves
    the lines (and the scratch files they name) of the entries before it.

    Entries before `start` are skipped (a call resumed with `--from`). Once
    `budget` seconds have passed, the next entry that would need a fetch is
    yielded as CONTINUE (with its `index`) and nothing after it is.

    Clears this label's scratch files first: they are only ever read in the run
    that wrote them, so anything left under `refetch/<label>-<n>.md` is an
    earlier run's and must not outlive this one's fetches by name. Only that
    exact shape: a glob on `<label>-*` would also take another label's files
    when one label is a prefix of the other (`fix` and `fix-x`). From `start`
    on only: an earlier call of the same run printed READ lines naming the ones
    before it.
    """
    refetch = repo_root / ".wikicommit" / ".cache" / "refetch"
    if refetch.is_dir():
        mine = re.compile(rf"{re.escape(label)}-(\d+)\.md")
        for stale in refetch.glob(f"{label}-*.md"):
            matched = mine.fullmatch(stale.name)
            if matched and int(matched.group(1)) >= start:
                stale.unlink(missing_ok=True)
    if not isinstance(entries, list):
        entries = []
    budgeted, state = _budgeted(fetch, budget, clock)
    for index, entry in enumerate(entries, start=1):
        if index < start:
            continue
        state["index"] = f"[{index}]"
        source_type = str(entry.get("type") or "").strip() if isinstance(entry, dict) else ""
        if source_type == "manual":
            yield {"index": index, "result": "MANUAL", "identifier": ""}
            continue
        key = "path" if source_type == "path" else "url"
        identifier = str(entry.get(key) or "").strip() if isinstance(entry, dict) else ""
        if source_type not in ("path", "url", "wikicommit") or not identifier:
            yield {
                "index": index, "result": "UNAVAILABLE", "reason": "invalid",
                "identifier": identifier or "-",
                "message": f"sources[{index}] has no usable type/{key}",
            }
            continue
        page_hash = str(entry.get("hash") or "").strip()
        try:
            outcome = obtain(
                "path" if source_type == "path" else "url",
                identifier, label, index, page_hash, repo_root, fetch=budgeted,
            )
        except _OutOfBudget:
            yield {"index": index, "result": "CONTINUE", "identifier": identifier}
            return
        yield {"index": index, "identifier": identifier, **outcome}


def format_entry(entry: dict) -> str:
    """One stdout line per entry; the keyword is the caller's next action."""
    n = f"[{entry['index']}]"
    result = entry["result"]
    if result == "READ":
        return f"READ: {n} {entry['file'].as_posix()} page={entry['page']}"
    if result == "EXTRACT":
        return f"EXTRACT: {n} {entry['file'].as_posix()}"
    if result == "RETRACTED":
        return f"RETRACTED: {n} {entry['identifier']} ({entry['management_file']})"
    if result == "MANUAL":
        return f"MANUAL: {n}"
    if result == "CONTINUE":
        return f"CONTINUE: next={entry['index']}"
    return f"UNAVAILABLE: {n} {entry['reason']} {entry['identifier']} ({entry['message']})"


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve a source's extracted-text cache path (reads the identifier from stdin)."
    )
    parser.add_argument(
        "--type",
        dest="source_type",
        choices=("url", "path"),
        default="url",
        help="Which kind of identifier is on stdin: a source.url (default) or a source.path.",
    )
    parser.add_argument(
        "--settle",
        metavar="FETCHED_FILE",
        help="For a URL fetched because no cache existed: compare FETCHED_FILE with the "
        "page's hash (--page-hash) and the management file's source.hash, and move it into "
        "the cache only when the latter matches. Never writes to a management file. "
        "URL sources only.",
    )
    parser.add_argument(
        "--page-hash",
        default="",
        help="With --settle / --obtain: the page's sources[].hash for this entry.",
    )
    parser.add_argument(
        "--obtain",
        action="store_true",
        help="Get one sources[] entry's text: retraction check, cache, fetch and settle in "
        "one step. Prints one READ: / EXTRACT: / RETRACTED: / UNAVAILABLE: line.",
    )
    parser.add_argument(
        "--obtain-sources",
        action="store_true",
        help="Read a page path from stdin and do --obtain for every entry of that page's "
        "sources, one line each, then a SUMMARY: line.",
    )
    parser.add_argument("--label", default="", help="With --obtain / --obtain-sources: the scratch-file label (review, fix).")
    parser.add_argument("--index", type=int, default=0, help="With --obtain: the entry's position in sources (1, 2, ...).")
    parser.add_argument(
        "--from", dest="start", type=int, default=1,
        help="With --obtain-sources: start at this entry (the n of a CONTINUE: next=<n> line).",
    )
    parser.add_argument(
        "--budget", type=float, default=45.0,
        help="With --obtain-sources: start no new fetch after this many seconds (default 45); "
        "the rest is left for a call with --from.",
    )
    args = parser.parse_args()

    identifier = sys.stdin.read().strip()
    if not identifier:
        print(
            "Usage: echo '<url|path>' | resolve_source_cache_path.py [--type url|path]",
            file=sys.stderr,
        )
        return 1

    if args.obtain_sources:
        if not _LABEL.match(args.label):
            print("ERROR: --obtain-sources needs --label <[a-z0-9-]+>", file=sys.stderr)
            return 1
        if args.start < 1 or args.budget < 0:
            print("ERROR: --from needs n >= 1 and --budget a non-negative number", file=sys.stderr)
            return 1
        # A `translated_from` written before the `.wikicommit/wiki/` ->
        # `.wikicommit/entity/` rename still holds the old prefix, and the
        # caller hands that value over as it is; every consumer of the field
        # tolerates both, so this does too.
        page = resolve_stored_entity_path(identifier)
        # The page whose sources are read must be a file in this repository;
        # its frontmatter is all that is read, but outside is outside.
        if not _inside(page, Path()) or not page.is_file():
            print(f"ERROR: {identifier} is not a page file in this repository", file=sys.stderr)
            return 1
        fm, err = parse_frontmatter(page)
        if fm is None:
            print(f"ERROR: {identifier}: {err}", file=sys.stderr)
            return 1
        counts = {key: 0 for key in ("READ", "EXTRACT", "RETRACTED", "UNAVAILABLE", "MANUAL")}
        resume = None
        for entry in iter_obtain_sources(
            fm.get("sources"), args.label, start=args.start, budget=args.budget
        ):
            if entry["result"] == "CONTINUE":
                resume = entry
                break
            counts[entry["result"]] += 1
            print(format_entry(entry), flush=True)
        print(
            f"SUMMARY: entries={sum(counts.values())} "
            + " ".join(f"{key.lower()}={value}" for key, value in counts.items())
        )
        if resume is not None:
            print(format_entry(resume))
        return 0

    if args.obtain:
        if not _LABEL.match(args.label) or args.index < 1:
            print("ERROR: --obtain needs --label <[a-z0-9-]+> and --index <n >= 1>", file=sys.stderr)
            return 1
        outcome = obtain(args.source_type, identifier, args.label, args.index, args.page_hash)
        if outcome["result"] == "RETRACTED":
            print(f"RETRACTED: {identifier} ({outcome['management_file']})")
            return 2
        if outcome["result"] == "UNAVAILABLE":
            print(f"UNAVAILABLE: {outcome['reason']} ({outcome['message']})")
            return 1
        if outcome["result"] == "EXTRACT":
            print(f"EXTRACT: {outcome['file'].as_posix()}")
            return 0
        print(f"READ: {outcome['file'].as_posix()} page={outcome['page']}")
        return 0

    if args.settle:
        if args.source_type != "url":
            print("ERROR: --settle applies to URL sources only", file=sys.stderr)
            return 1
        outcome = settle_fetch(identifier, Path(args.settle), args.page_hash)
        if outcome["result"] == "RETRACTED":
            print(f"RETRACTED: {identifier} ({outcome['management_file']})")
            return 2
        if outcome["result"] == "ERROR":
            print(f"ERROR: {outcome['message']}", file=sys.stderr)
            return 1
        print(
            f"SETTLED: page={outcome['page']}, cache={outcome['cache']}, "
            f"read={outcome['read'].as_posix()}"
        )
        return 0

    located = locate_path(identifier) if args.source_type == "path" else locate_url(identifier)

    if located.retracted:
        print(f"RETRACTED: {identifier} ({located.management_file})")
        return 2
    # Issue #1206: the caller answers UNREGISTERED / NO_CACHE on the `path`
    # route by reading the raw file, so a path that resolves outside the
    # repository must not reach either line. Before both, for the same reason
    # `--obtain` checks it before `missing`.
    if args.source_type == "path" and not _inside(Path() / identifier, Path()):
        print(f"OUTSIDE: {identifier}")
        return 1
    if located.management_file is None:
        print(f"UNREGISTERED: {identifier}")
        return 1
    if not located.cache_file.is_file():
        print(f"NO_CACHE: {located.cache_file.as_posix()} ({located.management_file.as_posix()})")
        return 1
    print(located.cache_file)
    return 0


def use_utf8_streams() -> None:
    """Write every line as UTF-8 whatever the locale, and read stdin as a file name.

    `run_fetch()` already reads the child's output as UTF-8 (Issue #1256), but a
    non-ASCII path or URL it hands back (or one from a page's `sources`) raised
    `UnicodeEncodeError` at this script's own `print` on a cp1252 terminal or
    pipe, after the child had succeeded. `skill_workflow.py`'s helper of the same
    name, with two differences:

    - stdout keeps the file-name error handler (`surrogateescape` on POSIX):
      under a POSIX locale a name read from the disk carries its undecodable
      bytes as surrogates, and they must go back out as the same bytes rather
      than raise.
    - stdin is decoded the way the OS decodes file names (UTF-8 on Windows and
      under a UTF-8 locale), not as UTF-8 outright: the identifier is opened as
      a path and passed in argv to `add_source.py`, and under a POSIX `C` locale
      a non-ASCII name only survives both as surrogates.
    """
    for stream, encoding, errors in (
        (sys.stdin, sys.getfilesystemencoding(), sys.getfilesystemencodeerrors()),
        # The OS's own handler for undecodable name bytes: `surrogateescape` on
        # POSIX, `surrogatepass` on Windows (a lone surrogate in an NTFS name is
        # not one `surrogateescape` can write).
        (sys.stdout, "utf-8", sys.getfilesystemencodeerrors()),
        (sys.stderr, "utf-8", "backslashreplace"),
    ):
        try:
            stream.reconfigure(encoding=encoding, errors=errors)
        except (AttributeError, ValueError, OSError, LookupError):
            pass


if __name__ == "__main__":
    use_utf8_streams()
    sys.exit(main())
