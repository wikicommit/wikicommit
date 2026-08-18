#!/usr/bin/env python3
"""
add_source.py — wikicommit-generate のバックエンドスクリプト。

ソースファイルまたは URL を .wikicommit/source/ 配下の管理ファイルとして登録する。
既存の管理ファイルが存在する場合はハッシュを比較して status を更新する。

Usage:
    python add_source.py <file_path>
    python add_source.py <https://url>
    python add_source.py <dir_path> --include "<glob_pattern>"
"""

import argparse
import glob
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# type: url / type: wikicommit ソースの markitdown フェッチに使う User-Agent。
# 既定の python-requests UA は Wikimedia 系ドメイン（Wikipedia/Wikisource 等）に
# 403 Forbidden で拒否されるため、WikiCommit を名乗る独自 UA を送る（Issue #527）。
USER_AGENT = "WikiCommit/1.0 (+https://github.com/wikicommit/wikicommit)"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def _sanitize_path_segment(segment: str) -> str:
    # Keep dots to distinguish blog.example.com from blog-example.com (both
    # would collapse to the same name if dots were also replaced with dashes).
    # Applied identically to the host and path halves so neither half is
    # sanitized more permissively than the other.
    return re.sub(r"[^\w\-.]", "-", segment)


def url_to_filename(url: str) -> str:
    """https://example.com/path/to/page → example.com/path-to-page

    Returns a relative path (hostname as directory, path segment as
    filename stem) so .wikicommit/source/url/ groups sources by site
    instead of flattening every URL into one directory (#191).

    A bare-domain URL (no path segment, e.g. "https://example.com") returns
    just the host, with no "/index" suffix. A real "/index" path (e.g.
    "https://example.com/index") sanitizes to the same "index" stem that an
    "/index" fallback would use, so a fixed fallback name would make the two
    distinct URLs collide on the same management file path (#213). Returning
    the bare host instead places the bare-domain management file as
    ".wikicommit/source/url/<host>.md", a sibling of the "<host>/" directory
    that holds paths — a name no sanitized real path can ever produce, since
    every real path lives one level deeper under "<host>/".

    Note: management files created before this change (or before non-ASCII
    decoding was added, #192) keep their old flat filename — there is no
    automatic migration. To move one, `git mv` it to the path this function
    now produces.
    """
    url = re.sub(r"^https?://", "", url)
    url = re.sub(r"[?#].*$", "", url)
    url = url.rstrip("/")
    # Decode only non-ASCII percent-encoded byte runs (%80-%FF) so CJK/etc.
    # path segments stay readable instead of turning into hex litter. ASCII
    # percent-encoding (e.g. %2F) is left encoded so it can't collapse onto a
    # literal separator once "/" becomes "-" below (would otherwise alias
    # "foo%2Fbar" and "foo/bar" to the same filename — #192).
    url = re.sub(r"(?:%[89A-Fa-f][0-9A-Fa-f])+", lambda m: unquote(m.group(0)), url)
    host, _, path = url.partition("/")
    host = _sanitize_path_segment(host)
    if not host:
        # No host (e.g. "https://" or "https:///foo") — refuse rather than
        # return a path starting with "/", which Path.__truediv__ would treat
        # as absolute and silently write outside repo_root.
        raise ValueError(f"URL に有効なホスト名が含まれていません: {url!r}")
    if not path:
        # Bare-domain URL (no path segment). Return just the host — see the
        # docstring for why this must not be "{host}/index" (#213).
        return host
    # Replace / with - for path separators within the path segment.
    path = path.replace("/", "-")
    path = _sanitize_path_segment(path)
    return f"{host}/{path}"


def ingest_path_for_file(source_path: str, repo_root: Path) -> Path:
    """ファイルソースの管理ファイルパスを計算する。"""
    p = Path(source_path)
    stem = p.with_suffix(".md")
    return repo_root / ".wikicommit" / "source" / "path" / stem


def ingest_path_for_url(url: str, repo_root: Path) -> Path:
    """URL ソースの管理ファイルパスを計算する。"""
    filename = url_to_filename(url) + ".md"
    return repo_root / ".wikicommit" / "source" / "url" / filename


def _yaml_single_quote(value: str) -> str:
    """Wrap value as a YAML single-quoted scalar, escaping embedded quotes.

    Single-quoted YAML strings have no backslash-escape processing (unlike
    double-quoted strings, where e.g. "\\0" is a NUL escape), so a stray
    backslash can never be misinterpreted — a defense-in-depth backstop for
    process_file() normalizing path separators to forward slashes (#269).
    """
    return "'" + value.replace("'", "''") + "'"


def build_frontmatter_file(source_path: str, file_hash: str) -> str:
    return f"""---
source:
  type: path
  path: {_yaml_single_quote(source_path)}
  hash: {file_hash}

schema:
status: pending
last_generated_at:
extracted_tokens:
generated_pages: []
failed_pages: []
---

"""


def build_frontmatter_url(url: str) -> str:
    return f"""---
source:
  type: url
  url: {_yaml_single_quote(url)}
  hash: ""

schema:
status: pending
last_generated_at:
extracted_tokens:
generated_pages: []
failed_pages: []
---

"""


def _frontmatter_slice(content: str) -> tuple[int, int]:
    """frontmatter テキストの開始・終了インデックスを返す。

    content[start:end] が --- フェンス間のテキストを指す。
    フロントマターが見つからない場合は (0, 0) を返す。
    """
    if not content.startswith("---\n"):
        return (0, 0)
    m = re.search(r"^---$", content[4:], re.MULTILINE)
    if not m:
        return (4, len(content))
    return (4, 4 + m.start())


def parse_frontmatter_hash(content: str) -> str | None:
    """管理ファイルの frontmatter から hash フィールドを抽出する。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^\s+hash:\s*(.+)$", fm, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def parse_frontmatter_status(content: str) -> str | None:
    """管理ファイルの frontmatter から status フィールドを抽出する。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^status:\s*(.+)$", fm, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def parse_frontmatter_source_type(content: str) -> str | None:
    """管理ファイルの frontmatter から source.type フィールドを抽出する。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^\s+type:\s*(.+)$", fm, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def update_frontmatter_status(content: str, new_status: str) -> str:
    """管理ファイルの status のみを更新する（hash は変更しない）。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    fm = re.sub(r"^(status:\s*).*$", rf"\g<1>{new_status}", fm, flags=re.MULTILINE)
    return content[:start] + fm + content[end:]


def update_frontmatter_hash(content: str, new_hash: str) -> str:
    """管理ファイルの source.hash のみを更新する（他フィールドは変更しない）。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    fm = re.sub(r"^(\s+hash:\s*).*$", rf"\g<1>{new_hash}", fm, count=1, flags=re.MULTILINE)
    return content[:start] + fm + content[end:]


def process_file(source_path: str, repo_root: Path) -> tuple[str, str, str]:
    """
    ファイルソースを処理して管理ファイルを生成または更新する。

    Returns:
        (result_code, ingest_path_str, message)
        result_code: "CREATED" | "SKIP" | "UPDATED" | "ERROR"
    """
    # A Windows-native caller may pass a backslash-separated relative path
    # (e.g. "pdfs\\04_foo.pdf"). Written verbatim into frontmatter, backslash
    # is a YAML escape character in double-quoted strings ("\0" → NUL),
    # corrupting the path; normalize to forward slashes up front so every
    # downstream use (Path construction, ingest path, YAML output) is
    # consistent regardless of the caller's OS (#269).
    source_path = source_path.replace("\\", "/")

    abs_source = repo_root / source_path
    if Path(source_path).is_absolute():
        err = f"ERROR: {source_path}: 絶対パスは使用できません。リポジトリルートからの相対パスを指定してください"
    elif not abs_source.exists():
        err = f"ERROR: {source_path}: ファイルが存在しません"
    elif not abs_source.is_file():
        err = f"ERROR: {source_path}: ファイルではありません"
    else:
        err = None
    if err:
        print(err, file=sys.stderr)
        return ("ERROR", source_path, "")

    ingest_file = ingest_path_for_file(source_path, repo_root)
    file_hash = sha256_file(str(abs_source))

    if not ingest_file.exists():
        ingest_file.parent.mkdir(parents=True, exist_ok=True)
        ingest_file.write_text(build_frontmatter_file(source_path, file_hash), encoding="utf-8")
        return ("CREATED", str(ingest_file.relative_to(repo_root)), "")

    existing = ingest_file.read_text(encoding="utf-8")
    existing_hash = parse_frontmatter_hash(existing)
    existing_status = parse_frontmatter_status(existing)

    ingest_rel = str(ingest_file.relative_to(repo_root))

    if existing_hash == file_hash:
        # ハッシュ一致 → outdated 状態なら pending に戻す（DesignDoc-data §4.3）
        if existing_status == "outdated":
            ingest_file.write_text(update_frontmatter_status(existing, "pending"), encoding="utf-8")
            return ("UPDATED", ingest_rel, "hash unchanged, status: outdated → pending")
        return ("SKIP", ingest_rel, "hash unchanged")

    # 既に outdated → hash は保持（前回生成時の参照点として機能する）
    if existing_status == "outdated":
        return ("SKIP", ingest_rel, "already outdated, source changed again")

    # pending / generated / partial / failed → status のみ outdated に遷移（hash は保持）
    ingest_file.write_text(update_frontmatter_status(existing, "outdated"), encoding="utf-8")
    return ("UPDATED", ingest_rel, "hash mismatch, status: outdated")


def process_url(url: str, repo_root: Path) -> tuple[str, str, str]:
    """
    URL ソースを処理して管理ファイルを生成する。

    URL ソースは hash を空文字列で作成する（URL ハッシュの更新は再実行で行う設計）。
    既存の管理ファイルがあり status が pending/outdated/partial（次に Pass 1 が処理する
    キューに既に入っている）なら SKIP する。status が generated/failed/excluded（前回の
    処理が完結済み）の場合は RECHECK を返す — このソースは Pass 1 が実際に再フェッチして
    ハッシュ比較するまで「変更されたかどうか」が判定不能なため（#310。管理ファイルの
    status/hash はここでは書き換えない — 再フェッチの結果 HASH_MATCH なら前回の状態の
    ままにしておく必要があるため）。
    """
    try:
        ingest_file = ingest_path_for_url(url, repo_root)
    except ValueError as e:
        print(f"ERROR: {url}: {e}", file=sys.stderr)
        return ("ERROR", url, "")

    if not ingest_file.exists():
        ingest_file.parent.mkdir(parents=True, exist_ok=True)
        ingest_file.write_text(build_frontmatter_url(url), encoding="utf-8")
        return ("CREATED", str(ingest_file.relative_to(repo_root)), "")

    ingest_rel = str(ingest_file.relative_to(repo_root))
    existing = ingest_file.read_text(encoding="utf-8")
    existing_status = parse_frontmatter_status(existing)

    if existing_status in ("generated", "failed", "excluded"):
        return ("RECHECK", ingest_rel, f"previous status: {existing_status}")

    return ("SKIP", ingest_rel, "already registered")


def write_hash(ingest_rel: str, content_file: str, repo_root: Path) -> tuple[str, str, str]:
    """
    フェッチ済みコンテンツ（--content-file）の SHA-256 を計算し、管理ファイルの
    source.hash に書き込む（type: url / type: wikicommit 向け）。

    WebFetch 自体はエージェントに委ねつつ、「計算して正しい書式で書き戻す」という
    決定論的な部分だけをスクリプトに切り出す（Issue #157・DesignDoc-skills.md §11.5）。

    Returns:
        (result_code, ingest_path_str, message)
        result_code: "HASH_WRITTEN" | "ERROR"
    """
    ingest_path = repo_root / ingest_rel
    if not ingest_path.is_file():
        return ("ERROR", ingest_rel, "管理ファイルが存在しません")

    content_path = Path(content_file)
    if not content_path.is_absolute():
        content_path = repo_root / content_path
    if not content_path.is_file():
        return ("ERROR", ingest_rel, f"コンテンツファイルが存在しません: {content_file}")

    existing = ingest_path.read_text(encoding="utf-8")
    source_type = parse_frontmatter_source_type(existing)
    if source_type not in ("url", "wikicommit"):
        return (
            "ERROR",
            ingest_rel,
            f"source.type が url/wikicommit ではありません（現在: {source_type}）",
        )

    new_hash = sha256_file(str(content_path))
    updated = update_frontmatter_hash(existing, new_hash)
    if parse_frontmatter_hash(updated) != new_hash:
        return (
            "ERROR",
            ingest_rel,
            "hash フィールドが見つからず書き込めません（frontmatter の形式を確認してください）",
        )
    ingest_path.write_text(updated, encoding="utf-8")
    return ("HASH_WRITTEN", ingest_rel, new_hash)


def check_hash(ingest_rel: str, content_file: str, repo_root: Path) -> tuple[str, str, str]:
    """
    キャッシュ済みスクラッチファイル（--content-file）の SHA-256 が、管理ファイルの
    現在の source.hash と一致するか確認する（type: url / type: wikicommit 向け）。

    一致すれば Pass 1 は markitdown の再フェッチ・write_hash をスキップし、
    スクラッチファイルの内容をそのまま抽出テキストとして再利用できる（Issue #278）。
    read-only（write_hash と異なり管理ファイルは変更しない）。

    Returns:
        (result_code, ingest_path_str, message)
        result_code: "HASH_MATCH" | "HASH_MISMATCH" | "ERROR"
    """
    ingest_path = repo_root / ingest_rel
    if not ingest_path.is_file():
        return ("ERROR", ingest_rel, "管理ファイルが存在しません")

    content_path = Path(content_file)
    if not content_path.is_absolute():
        content_path = repo_root / content_path
    if not content_path.is_file():
        return ("HASH_MISMATCH", ingest_rel, "スクラッチファイルが存在しません（キャッシュなし）")

    existing = ingest_path.read_text(encoding="utf-8")
    source_type = parse_frontmatter_source_type(existing)
    if source_type not in ("url", "wikicommit"):
        return (
            "ERROR",
            ingest_rel,
            f"source.type が url/wikicommit ではありません（現在: {source_type}）",
        )

    current_hash = parse_frontmatter_hash(existing)
    if not current_hash or current_hash == '""':
        return ("HASH_MISMATCH", ingest_rel, "source.hash が未設定です")

    scratch_hash = sha256_file(str(content_path))
    if scratch_hash == current_hash:
        return ("HASH_MATCH", ingest_rel, scratch_hash)
    return ("HASH_MISMATCH", ingest_rel, "hash不一致（ソース更新後の再フェッチが必要）")


def fetch_url(url: str, output: str, repo_root: Path) -> tuple[str, str, str]:
    """
    URL を WikiCommit 独自 User-Agent で `markitdown` の Python API 経由でフェッチ・変換し、
    結果を output に書き込む（type: url / type: wikicommit 向け。Issue #527）。

    `markitdown` CLI にそのまま URL を渡すと、内部で使う requests の既定 User-Agent が
    Wikimedia 系ドメインに 403 Forbidden で拒否される。`requests.Session` に独自 UA を
    設定し `MarkItDown(requests_session=...)` へ渡すことで、`convert_uri`/`convert_response`
    が本来行う HTTP レスポンスヘッダ（Content-Type の charset・mimetype）に基づく変換方式の
    自動判定はそのまま保ったまま UA だけを差し替える（curl 等でいったんローカルファイルに
    落としてから変換する方式は、この charset ヘッダの情報が失われ文字化けを起こすため採用しない）。

    Returns:
        (result_code, output_path_str, message)
        result_code: "FETCHED" | "ERROR"
    """
    import requests
    from markitdown import MarkItDown

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    md = MarkItDown(requests_session=session)

    try:
        result = md.convert_url(url)
    except Exception as e:  # noqa: BLE001 - surfaced verbatim as an extraction failure
        return ("ERROR", output, f"{type(e).__name__}: {e}")

    out_path = Path(output)
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result.text_content, encoding="utf-8")
    return ("FETCHED", str(out_path), "")


def _tally(result: str, path: str, msg: str, counts: dict) -> bool:
    """結果コードを表示してカウンタを更新する。エラーなら True を返す。"""
    if result == "CREATED":
        print(f"CREATED: {path}")
        counts["created"] += 1
    elif result == "SKIP":
        print(f"SKIP: {path} ({msg})")
        counts["skipped"] += 1
    elif result == "UPDATED":
        print(f"UPDATED: {path} ({msg})")
        counts["updated"] += 1
    elif result == "RECHECK":
        print(f"RECHECK: {path} ({msg})")
        counts["rechecked"] += 1
    else:
        return True
    return False


def main_from_args(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Register a source to .wikicommit/source/")
    parser.add_argument("source", nargs="?", help="File path, directory path, or https:// URL")
    parser.add_argument("--include", help="Glob pattern for directory scanning (e.g. '**/*.py')")
    parser.add_argument(
        "--write-hash",
        metavar="INGEST_FILE",
        help="Write the SHA-256 hash of --content-file into INGEST_FILE's source.hash field "
        "(for url/wikicommit sources, after fetching content). Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--check-hash",
        metavar="INGEST_FILE",
        help="Check whether --content-file's SHA-256 matches INGEST_FILE's current source.hash, "
        "without writing anything (read-only). Used to decide whether a cached scratch file from "
        "a previous run can be reused instead of re-fetching. Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--content-file",
        help="Path to a file holding fetched content; required with --write-hash or --check-hash",
    )
    parser.add_argument(
        "--fetch-url",
        metavar="URL",
        help="Fetch URL with markitdown using a WikiCommit User-Agent (avoids the 403s that "
        "Wikimedia domains return for markitdown's default User-Agent, #527) and write the "
        "converted Markdown to --output. Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--output",
        help="Path to write the fetched/converted content to; required with --fetch-url",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    if args.fetch_url:
        if not args.output:
            print("ERROR: --fetch-url requires --output", file=sys.stderr)
            return 1
        result, path, msg = fetch_url(args.fetch_url, args.output, repo_root)
        if result == "FETCHED":
            print(f"FETCHED: {path}")
            return 0
        print(f"ERROR: {args.fetch_url}: {msg}", file=sys.stderr)
        return 1

    if args.write_hash:
        if not args.content_file:
            print("ERROR: --write-hash requires --content-file", file=sys.stderr)
            return 1
        result, path, msg = write_hash(args.write_hash, args.content_file, repo_root)
        if result == "HASH_WRITTEN":
            print(f"HASH_WRITTEN: {path} ({msg})")
            return 0
        print(f"ERROR: {path}: {msg}", file=sys.stderr)
        return 1

    if args.check_hash:
        if not args.content_file:
            print("ERROR: --check-hash requires --content-file", file=sys.stderr)
            return 1
        result, path, msg = check_hash(args.check_hash, args.content_file, repo_root)
        if result == "HASH_MATCH":
            print(f"HASH_MATCH: {path} ({msg})")
            return 0
        if result == "HASH_MISMATCH":
            print(f"HASH_MISMATCH: {path} ({msg})")
            return 1
        print(f"ERROR: {path}: {msg}", file=sys.stderr)
        return 1

    source = args.source
    if not source:
        print(
            "ERROR: source is required unless --write-hash/--check-hash/--fetch-url is given",
            file=sys.stderr,
        )
        return 1
    counts: dict = {"created": 0, "updated": 0, "skipped": 0, "rechecked": 0}
    has_error = False

    if source.startswith("https://") or source.startswith("http://"):
        result, path, msg = process_url(source, repo_root)
        has_error = _tally(result, path, msg, counts)
    elif args.include:
        source_dir = Path(source)
        if not (repo_root / source_dir).is_dir():
            print(f"ERROR: {source}: ディレクトリが存在しません", file=sys.stderr)
            return 1
        pattern = str(repo_root / source_dir / args.include)
        matched = [p for p in glob.glob(pattern, recursive=True) if Path(p).is_file()]
        if not matched:
            print(f"WARNING: {source}/{args.include}: マッチするファイルがありません", file=sys.stderr)
        for abs_path in sorted(matched):
            # .as_posix() (not str()) so Windows callers get forward slashes
            # here too, matching process_file()'s own normalization (#269).
            rel_path = Path(abs_path).relative_to(repo_root).as_posix()
            result, path, msg = process_file(rel_path, repo_root)
            if _tally(result, path, msg, counts):
                has_error = True
    else:
        result, path, msg = process_file(source, repo_root)
        has_error = _tally(result, path, msg, counts)

    c, u, s, r = counts["created"], counts["updated"], counts["skipped"], counts["rechecked"]
    print(f"SUMMARY: created={c}, updated={u}, skipped={s}, rechecked={r}")
    return 1 if has_error else 0


def main() -> int:
    return main_from_args()


if __name__ == "__main__":
    sys.exit(main())
