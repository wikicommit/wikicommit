#!/usr/bin/env python3
"""
resolve_source_cache_path.py — wikicommit-ask の `--include-source`（Issue #470）
バックエンドスクリプト。

sources[].url から、対応する .wikicommit/.cache/ingest-fetch/ 配下の
フェッチキャッシュファイルの実在パスを特定する。

`wikicommit-generate`（Pass 1「Hash write-back」）の scratch-path は
「ingest 管理ファイルの実際の相対パス（.wikicommit/source/url/ からの相対、
拡張子なし）」として定義される — URL から `add_source.py` の
`url_to_filename()` で再計算した名前ではない。URL から直接再計算すると、
Issue #191 より前に登録された旧フラット命名の管理ファイル
（自動移行されない。docs/DesignDoc-data.md §4.3）で実際の scratch-path と
食い違い、実在するキャッシュを「見つからない」と誤判定する。本スクリプトは
代わりに .wikicommit/source/url/ 配下を実際に走査し、`source.url` が一致する
管理ファイルを見つけて、その実パスから scratch-path を導出する（新旧どちらの
命名形式が混在していても正しく解決できる）。

Usage:
    echo "<url>" | python resolve_source_cache_path.py

Reads the URL from stdin (not argv — see docs/DesignDoc-skills.md §11.7:
sources[].url is only format-validated by validate_frontmatter.py, not
verified safe for shell-argument use). Prints the cache file path
(.wikicommit/.cache/ingest-fetch/<scratch-path>.md, repo-root-relative) on
stdout if a matching ingest management file is found AND the corresponding
cache file exists on disk. Otherwise prints nothing.

Exit codes:
    0 — cache file found and printed
    1 — no matching ingest management file, or the cache file doesn't exist
"""

import sys
from pathlib import Path

sys.path.insert(0, ".wikicommit/scripts")
from _frontmatter import parse_frontmatter  # noqa: E402


def resolve(target_url: str, repo_root: Path = Path()) -> Path | None:
    ingest_root = repo_root / ".wikicommit" / "source" / "url"
    if not ingest_root.is_dir():
        return None

    for management_file in ingest_root.rglob("*.md"):
        fm, _err = parse_frontmatter(management_file)
        if not fm:
            continue
        source = fm.get("source")
        if not isinstance(source, dict) or source.get("url") != target_url:
            continue
        scratch_path = management_file.relative_to(ingest_root).with_suffix("")
        cache_file = (repo_root / ".wikicommit" / ".cache" / "ingest-fetch" / scratch_path).with_suffix(".md")
        return cache_file if cache_file.is_file() else None

    return None


def main() -> int:
    target_url = sys.stdin.read().strip()
    if not target_url:
        print("Usage: echo '<url>' | resolve_source_cache_path.py", file=sys.stderr)
        return 1

    cache_file = resolve(target_url)
    if cache_file is None:
        return 1
    print(cache_file)
    return 0


if __name__ == "__main__":
    sys.exit(main())
