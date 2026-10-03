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
    0 — キャッシュが見つかり印字した（`--settle` では判定を印字した）
    1 — 一致する管理ファイルが無い（`UNREGISTERED:`）、またはキャッシュファイルが
        実在しない（`NO_CACHE:`）。`--settle` では引数の誤り・取得ファイルが無い
    2 — 管理ファイルが `status: retracted` である
        （`RETRACTED: <識別子> (<管理ファイルのパス>)` を印字。後者は
        人間が書いた `## Retraction Reason` の在り処である）
"""

import argparse
import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, ".wikicommit/scripts")
from _frontmatter import parse_frontmatter  # noqa: E402


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
        if not isinstance(source, dict) or source.get(key) != target:
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
    page_match = bool(page_hash) and got == page_hash.strip()

    if located.management_file is None:
        cache = "not-placed (no management file is registered for this URL)"
        read = fetched
    else:
        source = located.frontmatter.get("source") or {}
        recorded = str(source.get("hash") or "").strip().strip('"')
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
        "page": "match" if page_match else "mismatch",
        "cache": cache,
        "read": read,
        "hash": got,
    }


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
        help="With --settle: the grounding page's sources[].hash for this URL.",
    )
    args = parser.parse_args()

    identifier = sys.stdin.read().strip()
    if not identifier:
        print(
            "Usage: echo '<url|path>' | resolve_source_cache_path.py [--type url|path]",
            file=sys.stderr,
        )
        return 1

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
    if located.management_file is None:
        print(f"UNREGISTERED: {identifier}")
        return 1
    if not located.cache_file.is_file():
        print(f"NO_CACHE: {located.cache_file.as_posix()} ({located.management_file.as_posix()})")
        return 1
    print(located.cache_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
