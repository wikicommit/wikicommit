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
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

# type: url / type: wikicommit ソースの markitdown フェッチに使う User-Agent。
# 既定の python-requests UA は Wikimedia 系ドメイン（Wikipedia/Wikisource 等）に
# 403 Forbidden で拒否されるため、WikiCommit を名乗る独自 UA を送る（Issue #527）。
USER_AGENT = "WikiCommit/1.0 (+https://github.com/wikicommit/wikicommit)"

# 取り込み元ドメイン → そのサイトが自サイトのコンテンツ全体に対して明示している
# ライセンスの SPDX 識別子（Issue #558）。`KNOWN_JS_SHELL_DOMAINS`
# (.wikicommit/scripts/check_extraction_quality.py) と同じ「確認済みのものだけを
# 決定論的な対応表に持つ」パターンで、登録時に `source.license` の初期値を埋める
# ためだけに使う。ここに無いドメインは空欄のまま登録され、必要なら人間が
# 管理ファイルを直接編集する（WikiCommit はライセンスの当否を判断しない）。
#
# キーは登録可能ドメイン相当の接尾辞で、`license_for_url()` がホストの左ラベルを
# 順に落としながら照合する（`it.wikipedia.org` → `wikipedia.org` に一致）。
# 個別ページが別ライセンスを宣言していることはあるため（Wikimedia 系でも
# 引用文・画像・一部の転載記事は別条件）、値はあくまで既定値として扱う。
KNOWN_SOURCE_LICENSES = {
    "wikipedia.org": "CC-BY-SA-4.0",
    "wikisource.org": "CC-BY-SA-4.0",
    "wiktionary.org": "CC-BY-SA-4.0",
    "wikibooks.org": "CC-BY-SA-4.0",
    "wikiquote.org": "CC-BY-SA-4.0",
    "wikivoyage.org": "CC-BY-SA-4.0",
    "wikinews.org": "CC-BY-2.5",
    "wikidata.org": "CC0-1.0",
}


# ShareAlike 系ライセンスの識別子接頭辞（#570）。この表にあるライセンスのソース
# 「だけ」から作られたページは、そのライセンスでの提供義務を継承する。値は自由記述
# なので完全な判定はできないが、既知ドメイン対応表が返す値と SPDX の一般的な綴りは
# 覆う。取りこぼしの劣化は「注意書きが出ない」で済み、誤った注意書きは出ない側に倒す。
SHARE_ALIKE_LICENSE_PREFIXES = ("cc-by-sa", "cc-sa", "gfdl", "odbl", "cc-by-nc-sa")


# 静的取得で「本文は取れるが、ページが載せている内容の一部が黙って落ちる」ことが
# 確認済みの URL 形（#715）。値は「何が落ちるか」の一文で、登録時に一度だけ知らせる
# ためだけに使う（`is_share_alike()` の注意書きと同じ形）。
#
# これは**ガードではない** — ブロックせず、`status` も変えず、取得も止めない。
# `check_extraction_quality.py` の 3 ガードはいずれも「そもそも取得できるか／取れた
# ものがゴミか」を判定して Pass 1 の分岐を左右するが、ここで扱うのは「取得は成功し、
# 取れた本文も本物で、ただし別の一部が欠ける」という、取得後のテキストからは原理的に
# 見分けられない partial extraction（#574 が YouTube について定義した失敗クラスの
# 2 例目）である。本文だけで十分なソースは実在するため、止めるのではなく知らせる。
#
# 判定はホストとパスの形だけで決まる決定論的なもので、`KNOWN_SOURCE_LICENSES` と同じ
# 「確認済みのものだけを表に持つ」パターンに従う。ただし `KNOWN_JS_SHELL_DOMAINS` の
# 「確認済みのみ」規則をそのまま持ち込みはしない — あちらは誤ったエントリが取得自体を
# 飛ばす（実害がある）のに対し、こちらの誤りは余計な注意書きが 1 行出るだけであり、
# 取りこぼしの方（この Issue が直そうとしている黙った欠落）が明確に重い。非対称の
# 向きが逆なので、規則も同じにはならない。
_GITHUB_THREAD_PATH_RE = re.compile(r"^/[^/]+/[^/]+/(?:issues|pull)/\d+(?:/|$)")

# ホスト（登録可能ドメイン相当の接尾辞）→ (パス判定, 何が落ちるか)。
PARTIAL_EXTRACTION_URL_NOTES = (
    (
        "github.com",
        _GITHUB_THREAD_PATH_RE,
        "only the issue/PR body is extracted — every comment on the thread is "
        "dropped without an error. Register this only if the body alone is the "
        "source you want",
    ),
)


def host_suffix_candidates(url: str) -> list[str]:
    """URL のホストを、左ラベルを順に落とした接尾辞の列（具体的な順）で返す。

    `it.wikipedia.org` → `["it.wikipedia.org", "wikipedia.org"]`。末尾 1 ラベル
    （TLD 単独）は含めない。ホスト表を引く箇所（`license_for_url()` /
    `partial_extraction_note()`）はすべてこれを共有する — 同じ導出を各所に複製
    すると、片方だけホスト解析の端ケースを直したときに黙ってずれるため。
    """
    host = urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]
    if not host:
        return []
    labels = host.split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)]


def partial_extraction_note(url: str) -> str:
    """URL が既知の partial extraction 形なら「何が落ちるか」を返す。無ければ空文字列。

    ホストの照合は `license_for_url()` と同じく左ラベルを順に落としながら行い
    （`host_suffix_candidates()` を共有する）、パスは対応する正規表現で判定する。
    `github.com` を丸ごと対象にはしない — README・blob・release の取得は実際に
    完全なので、そこで注意書きを出すのは誤りであり、最も多い GitHub URL の形を
    ノイズで埋めることになる。
    """
    candidates = set(host_suffix_candidates(url))
    if not candidates:
        return ""
    path = urlsplit(url).path or "/"
    for domain, path_re, note in PARTIAL_EXTRACTION_URL_NOTES:
        if domain in candidates and path_re.search(path):
            return note
    return ""


def is_share_alike(license_id: str) -> bool:
    """ライセンス識別子が ShareAlike 系かどうかを返す（#570）。"""
    normalized = license_id.strip().lower()
    return any(normalized.startswith(prefix) for prefix in SHARE_ALIKE_LICENSE_PREFIXES)


def append_note(existing: str, addition: str) -> str:
    """`CREATED:` メッセージに注意書きを 1 件足す（区切りは `; `）。

    登録時の通知は複数（退避したパス・ライセンス・ShareAlike・partial extraction）
    が同時に立ちうるため、どれか 1 つが他を上書きしないよう常にここで連結する。
    """
    return f"{existing}; {addition}" if existing else addition


def license_for_url(url: str) -> str:
    """URL のホストから既知ライセンスの SPDX 識別子を引く。未知なら空文字列。

    候補は最も具体的なホストから順に見る（`www.a.wikipedia.org` より
    `wikipedia.org` を後に評価する）— 表に両方があれば具体的な方を採るため。
    """
    for candidate in host_suffix_candidates(url):
        if candidate in KNOWN_SOURCE_LICENSES:
            return KNOWN_SOURCE_LICENSES[candidate]
    return ""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def read_management_file(path: Path) -> str | None:
    """管理ファイルをテキストとして読む。読めない場合は None を返す。

    エンコーディングは `utf-8-sig` を使う — 一部の Windows エディタが書き戻した
    BOM 付きの管理ファイルを plain `utf-8` で読むと、先頭に BOM 文字が残るため
    `_frontmatter_slice()` が frontmatter を検出できず、`source.path` / `hash` が
    どれも読み取れなくなる（`.wikicommit/scripts/_frontmatter.py` が同じ理由で
    utf-8-sig に統一しているのと同じ問題。このスクリプトは自己完結のため import
    できず、方針だけを踏襲する）。同一性走査でこれが起きると、既存の管理ファイル
    が見つからないまま「導出先が別ソースに占有されている」と誤判定され、同じ
    ソースに対する2つ目の管理ファイルが作られてしまう。
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


# Query parameters that identify *how a reader arrived at* a URL rather than
# *which document it is*. They are dropped before a URL is turned into a
# filename or compared for identity (#572), so that the same article shared
# through two different campaigns still resolves to one management file. The
# denylist is inherently incomplete; a parameter it misses costs a second
# management file for the same document, never a wrong source (which is the
# failure mode #572 exists to eliminate).
_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "gclsrc",
        "dclid",
        "msclkid",
        "yclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "_ga",
        "ref_src",
        "s_kwcid",
    }
)

# Maximum length, in bytes, of the derived filename stem before the truncation
# path below kicks in. ext4 and most other filesystems cap a single name at 255
# bytes; the headroom left over covers ".md" plus the "-<sha8>" suffix that
# truncation adds. Bytes, not characters, because a stem can hold decoded
# non-ASCII path segments (#192) that cost up to 4 bytes each.
_MAX_STEM_BYTES = 200

# Length of the SHA-256 prefix appended to a derived filename when it has to be
# truncated (#572) or moved aside because a different source already occupies
# that name (#572 for URLs, #573 for paths).
_HASH_SUFFIX_LEN = 8


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_PARAMS or lowered.startswith(_TRACKING_PARAM_PREFIXES)


def normalize_url_for_identity(url: str) -> str:
    """Return the form of a URL used for filename derivation and identity.

    Two URLs that normalize to the same string are treated as the same source.
    This is used *only* internally: the ``source.url`` frontmatter field always
    records the URL exactly as the user supplied it, so provenance stays
    verbatim (#572).

    Normalization drops the fragment (never sent to a server, so it cannot
    select different content), drops tracking parameters, and sorts the
    remaining query parameters so that reordering them doesn't create a second
    source. Host and path are deliberately left alone — treating
    ``youtu.be/<id>`` and ``youtube.com/watch?v=<id>`` as one source needs
    site-specific knowledge and is explicitly out of scope for #572.
    """
    url = url.split("#", 1)[0]
    base, sep, query = url.partition("?")
    # Strip trailing slashes from the path only. Doing it to the whole string
    # would turn a hostless "https://" into "https:", which url_to_filename
    # would then sanitize into a bogus host instead of rejecting (#213 guard).
    scheme_match = re.match(r"^https?://", base)
    scheme = scheme_match.group(0) if scheme_match else ""
    base = scheme + base[len(scheme):].rstrip("/")
    if not sep:
        return base
    kept = sorted(
        (k, v) for k, v in parse_qsl(query, keep_blank_values=True) if not _is_tracking_param(k)
    )
    if not kept:
        return base
    return f"{base}?{urlencode(kept)}"


def _url_hash_suffix(normalized_url: str) -> str:
    return hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LEN]


def _path_hash_suffix(normalized_source_path: str) -> str:
    return hashlib.sha256(normalized_source_path.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LEN]


def _truncate_stem(stem: str, suffix: str) -> str:
    """Cut ``stem`` so that ``stem + "-" + suffix`` fits in _MAX_STEM_BYTES.

    Truncation happens on a character boundary, so a decoded multi-byte
    segment is never split into invalid UTF-8.
    """
    budget = _MAX_STEM_BYTES - len(suffix) - 1
    encoded = stem.encode("utf-8")[:budget]
    # Drop any trailing bytes left over from a partially-included character.
    truncated = encoded.decode("utf-8", errors="ignore")
    return f"{truncated}-{suffix}"


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

    The query string is kept (#572), because many sites identify a document
    only by a query parameter — every "https://www.youtube.com/watch?v=<id>"
    used to collapse onto the same "watch" stem, so registering a second video
    silently reported success against the first video's management file. The
    query is normalized first (see normalize_url_for_identity) so tracking
    parameters and parameter order don't split one document across two files,
    then folded into the stem: "watch?v=abc" → "watch-v-abc". A URL with no
    query derives exactly the same name as before, so this is backward
    compatible.

    Note: management files created before this change (or before non-ASCII
    decoding was added, #192) keep their old flat filename — there is no
    automatic migration, and none is needed: process_url() identifies an
    existing source by scanning for a matching source.url rather than by
    recomputing this name (#572).
    """
    normalized = normalize_url_for_identity(url)
    url = re.sub(r"^https?://", "", normalized)
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
        raise ValueError(f"URL has no valid host name: {url!r}")
    if not path:
        # Bare-domain URL (no path segment). Return just the host — see the
        # docstring for why this must not be "{host}/index" (#213). A bare
        # domain carrying only a query (e.g. "https://example.com?p=1") also
        # lands here, with the query already folded into the host half by
        # partition("/") ("example.com-p-1"), so it still keeps its own stem
        # as a sibling of the "<host>/" directory. That stem needs the same
        # length guard as the path branch below — without it a long query on a
        # bare domain produces a name past the filesystem's 255-byte limit and
        # surfaces as an OSError instead of a usable file (#572).
        if len(host.encode("utf-8")) > _MAX_STEM_BYTES:
            host = _truncate_stem(host, _url_hash_suffix(normalized))
        return host
    # Replace / with - for path separators within the path segment.
    path = path.replace("/", "-")
    path = _sanitize_path_segment(path)
    if len(path.encode("utf-8")) > _MAX_STEM_BYTES:
        # A long query (session tokens, signed URLs) can push the stem past the
        # filesystem's 255-byte name limit, which would surface as an OSError
        # rather than a usable error. Truncate and disambiguate with a hash of
        # the normalized URL, so two long URLs sharing a prefix stay distinct
        # (#572). Readability is sacrificed, but the source.url frontmatter
        # field still records the URL in full.
        path = _truncate_stem(path, _url_hash_suffix(normalized))
    return f"{host}/{path}"


def mgmt_path_for_file(source_path: str, repo_root: Path) -> Path:
    """ファイルソースの管理ファイルパスを計算する。

    元の拡張子は捨てずに保持し、".md" を付け足す（"raw/paper.pdf" →
    ".wikicommit/source/path/raw/paper.pdf.md"）。以前は `with_suffix(".md")`
    で拡張子を置き換えていたため、"raw/paper.pdf" と "raw/paper.docx" が同じ
    管理ファイルに解決され、後から登録した方が既存ソースを status: outdated に
    誤って書き換えていた（#573）。付け足す方式では、管理ファイルパスがソース
    パスと1対1に対応するため、この衝突が構造的に起こらなくなる。

    Note: この変更以前に登録された管理ファイルは拡張子なしの旧名のまま残る —
    自動移行はしない（#191・#192 と同じ方針）。process_file() は導出名ではなく
    source.path の走査で既存管理ファイルを特定するため、旧名のままでも二重登録に
    ならない（#573）。
    """
    rel = PurePosixPath(normalize_source_path(source_path))
    name = f"{rel.name}.md"
    if len(name.encode("utf-8")) > _MAX_STEM_BYTES:
        # Appending ".md" (rather than replacing the extension, as before)
        # makes the derived name 3 bytes longer than the source filename, so a
        # source file whose own name is already at the filesystem's 255-byte
        # limit would now fail the write with a bare OSError. Truncate and
        # disambiguate with a hash of the source path, exactly as
        # url_to_filename() does for over-long URL stems (#572); identity no
        # longer depends on this name being reconstructible (#573), so the
        # truncation is safe.
        name = f"{_truncate_stem(rel.name, _path_hash_suffix(str(rel)))}.md"
    return repo_root / ".wikicommit" / "source" / "path" / rel.parent / name


def normalize_source_path(source_path: str) -> str:
    """`source.path` の同一性比較に使う正規形を返す。

    Windows ネイティブの呼び出し元が渡すバックスラッシュ区切り（#269）と、
    先頭の "./" だけを吸収する。それ以上の正規化（シンボリックリンク解決・
    大文字小文字の畳み込み等）は行わない — frontmatter に書かれた文字列を
    そのまま照合するのが原則で、実体解決まで踏み込むと「別パスから同じ実体を
    指す」ケースの扱いという別の設計判断が必要になるため。
    """
    normalized = source_path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def build_source_path_index(repo_root: Path) -> dict[str, Path]:
    """`.wikicommit/source/path/` を1回だけ走査し、`source.path` の正規形から管理
    ファイルへの対応表を作る。

    走査結果を1回の実行の中で使い回せるようにするための切り出し（`--include` に
    よるディレクトリ一括登録は process_file() を N 回呼ぶため、呼び出しごとに
    全走査すると読み込み回数が N^2 に膨らむ）。同じキーに複数の管理ファイルが
    対応する場合は、パス昇順で最初に見つかったものを優先する。
    """
    index: dict[str, Path] = {}
    mgmt_root = repo_root / ".wikicommit" / "source" / "path"
    if not mgmt_root.is_dir():
        return index

    for management_file in sorted(mgmt_root.rglob("*.md")):
        content = read_management_file(management_file)
        if content is None:
            continue
        existing_path = parse_frontmatter_source_path(content)
        if existing_path:
            index.setdefault(normalize_source_path(existing_path), management_file)
    return index


def find_mgmt_file_for_path(
    source_path: str, repo_root: Path, index: dict[str, Path] | None = None
) -> Path | None:
    """既に同じソースパスを登録している管理ファイルを、実ディレクトリ走査で探す。

    同一性キーは導出ファイル名ではなく `source.path` そのものとする（#573。
    `type: url` 側で先に同じ移行を行った #572 と同じ柱）。導出名を同一性キーに
    使っていたため、拡張子違いの別ファイルを登録すると既存の管理ファイルが
    ハッシュ不一致経路に入り、登録したはずのファイルはどこにも記録されないまま
    無関係な既存ソースが status: outdated に書き換えられていた。

    実ファイルを走査するため、拡張子を含まない旧命名（本 Issue 以前）の管理
    ファイルも自動移行なしでヒットする。
    """
    if index is None:
        index = build_source_path_index(repo_root)
    return index.get(normalize_source_path(source_path))


def mgmt_path_for_url(url: str, repo_root: Path) -> Path:
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


def _license_line(license_id: str) -> str:
    """`source.license` の行を組み立てる（未知なら値なしの空欄で書き出す）。"""
    return f"  license: {_yaml_single_quote(license_id)}" if license_id else "  license:"


def build_frontmatter_file(source_path: str, file_hash: str, license_id: str = "") -> str:
    return f"""---
source:
  type: path
  path: {_yaml_single_quote(source_path)}
  hash: {file_hash}
{_license_line(license_id)}

schema:
status: pending
last_generated_at:
extracted_tokens:
generated_pages: []
failed_pages: []
---

"""


def build_frontmatter_url(url: str, license_id: str = "") -> str:
    return f"""---
source:
  type: url
  url: {_yaml_single_quote(url)}
  hash: ""
{_license_line(license_id)}

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


RETRACTION_REASON_RE = re.compile(
    r"^## Retraction Reason\r?\n(.*?)(?=\n## |\Z)", re.DOTALL | re.MULTILINE
)


def parse_retraction_reason(content: str) -> str:
    """管理ファイルの `## Retraction Reason` セクション本文を1行に畳んで返す（Issue #737）。

    `status: retracted` は人間にしか書けない値であり（証拠拘束ルール〈Issue #442〉の
    下で機械はソースを疑えない）、なぜ取り下げたかは enum ではなく散文で残す
    — 本 Issue の範囲では機械は報告しかせず、理由で分岐する消費者がいないため
    （`## Failure Reason`〈Issue #408〉と同じ形）。

    結果は `RETRACTED: <path> (<msg>)` という1行の結果コード契約に埋め込むため、
    改行・連続空白を単一の半角空白へ潰し、長い場合は切り詰める。セクションが無い
    場合は空文字列を返す — 呼び出し側はその場合「理由の記載なし」と伝える。
    """
    m = RETRACTION_REASON_RE.search(content)
    if not m:
        return ""
    collapsed = " ".join(m.group(1).split())
    if len(collapsed) > 200:
        collapsed = collapsed[:197] + "..."
    return collapsed


def retracted_result(mgmt_rel: str, content: str) -> tuple[str, str, str]:
    """`status: retracted` な管理ファイルに対する共通の結果コードを組み立てる。

    `SKIP` に落とさないことが要点である（Issue #737 の穴 (2)）。`SKIP: already
    registered` は「なぜ使えないのか」を一切伝えないため、人間が同じソースを
    もう一度登録しようとしたときに取り下げの事実が黙って握り潰される。
    """
    reason = parse_retraction_reason(content)
    detail = f"reason: {reason}" if reason else "no ## Retraction Reason recorded"
    return ("RETRACTED", mgmt_rel, f"previously retracted by a human — {detail}")


def parse_frontmatter_has_failed_pages(content: str) -> bool:
    """管理ファイルの failed_pages が非空かどうかを返す（#567）。

    `partial` が「再試行に意味がある（生成失敗を含む）」のか「同じ条件では
    もう進展しない（theme 除外のみ）」のかを分ける唯一の手がかり。前者だけが
    引数なし実行の収集対象に残る。

    フロー形式（`failed_pages: []` / `[a, b]`）とブロック形式（次行以降の
    `  - ...`）の両方を読む。Pass 4 が書くのは前者だが、人間が手で編集した
    ファイルは後者になりうる。値が読めなければ False を返す — 判定できない
    ものを「再試行の余地あり」と見なすと、進展しないファイルが枠を占め続ける
    という本 Issue の症状がそのまま戻るため、安全側は False。
    """
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^failed_pages:[ \t]*(.*)$", fm, re.MULTILINE)
    if m is None:
        return False
    inline = m.group(1).strip()
    if inline:
        return inline not in ("[]", "~", "null")
    rest = fm[m.end():]
    for line in rest.splitlines():
        if not line.strip():
            continue
        return line.startswith((" ", "\t")) and line.strip().startswith("- ")
    return False


def parse_frontmatter_source_type(content: str) -> str | None:
    """管理ファイルの frontmatter から source.type フィールドを抽出する。"""
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^\s+type:\s*(.+)$", fm, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def _unquote_yaml_scalar(value: str) -> str:
    """_yaml_single_quote() の逆。引用符が付いていない旧形式はそのまま返す。"""
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter_source_url(content: str) -> str | None:
    """管理ファイルの frontmatter から source.url フィールドを抽出する。

    build_frontmatter_url() は値を YAML 単一引用符スカラーとして書くため、
    引用符付きの値はアンクォートして返す（引用符内の '' は ' に戻す）。
    引用符が付いていない旧形式の管理ファイルはそのままの値を返す。
    """
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^\s+url:\s*(.+)$", fm, re.MULTILINE)
    if not m:
        return None
    return _unquote_yaml_scalar(m.group(1).strip())


def parse_frontmatter_source_path(content: str) -> str | None:
    """管理ファイルの frontmatter から source.path フィールドを抽出する。

    parse_frontmatter_source_url() と同じく、YAML 単一引用符スカラーはアンクォート
    して返す（引用符なしの旧形式はそのまま返す）。
    """
    start, end = _frontmatter_slice(content)
    fm = content[start:end]
    m = re.search(r"^\s+path:\s*(.+)$", fm, re.MULTILINE)
    if not m:
        return None
    return _unquote_yaml_scalar(m.group(1).strip())


def find_mgmt_file_for_url(url: str, repo_root: Path) -> Path | None:
    """既に同じ URL を登録している管理ファイルを、実ディレクトリ走査で探す。

    同一性キーは導出ファイル名ではなく `source.url` そのものとする（#572）。
    導出名を同一性キーに使うと、異なる URL がたまたま同じ名前に解決された場合に
    「登録済み」と誤判定し、しかも status が generated/failed/excluded なら
    RECHECK として *別の URL* を再フェッチしてしまう（silent wrong-source）。

    実ファイルを走査するため、Issue #191 以前の旧フラット命名・Issue #192 以前の
    パーセントエンコード命名・#572 以前にクエリを落として作られた管理ファイルの
    いずれも自動移行なしでヒットする（`resolve_source_cache_path.py` が参照側で
    先に採っている方式と同じ）。走査コストは URL ソース件数に対して線形だが、
    登録時の1回きりで実用上問題にならない。
    """
    mgmt_root = repo_root / ".wikicommit" / "source" / "url"
    if not mgmt_root.is_dir():
        return None

    target = normalize_url_for_identity(url)
    for management_file in sorted(mgmt_root.rglob("*.md")):
        content = read_management_file(management_file)
        if content is None:
            continue
        existing_url = parse_frontmatter_source_url(content)
        if existing_url and normalize_url_for_identity(existing_url) == target:
            return management_file
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


def process_file(
    source_path: str,
    repo_root: Path,
    index: dict[str, Path] | None = None,
    license_override: str = "",
) -> tuple[str, str, str]:
    """
    ファイルソースを処理して管理ファイルを生成または更新する。

    `index` は build_source_path_index() が返す対応表。一括登録のように短時間に
    何度も呼ぶ場合に渡すと走査を1回で済ませられる（新規作成分はこの関数が
    追記して最新に保つ）。省略時は呼び出しごとに走査する。

    Returns:
        (result_code, mgmt_path_str, message)
        result_code: "CREATED" | "SKIP" | "UPDATED" | "RETRACTED" | "ERROR"
    """
    # A Windows-native caller may pass a backslash-separated relative path
    # (e.g. "pdfs\\04_foo.pdf"). Written verbatim into frontmatter, backslash
    # is a YAML escape character in double-quoted strings ("\0" → NUL),
    # corrupting the path; normalize to forward slashes up front so every
    # downstream use (Path construction, management-file path, YAML output) is
    # consistent regardless of the caller's OS (#269).
    # The same normalization is what identity comparison uses (#573), so
    # applying it up front keeps the stored source.path, the derived
    # management-file path, and the lookup key in agreement.
    source_path = normalize_source_path(source_path)

    abs_source = repo_root / source_path
    if Path(source_path).is_absolute():
        err = f"ERROR: {source_path}: absolute paths are not accepted; give a path relative to the repository root"
    elif not abs_source.exists():
        err = f"ERROR: {source_path}: file does not exist"
    elif not abs_source.is_file():
        err = f"ERROR: {source_path}: is not a file"
    else:
        err = None
    if err:
        print(err, file=sys.stderr)
        return ("ERROR", source_path, "")

    file_hash = sha256_file(str(abs_source))

    # 同一性はファイル名ではなく source.path で判定する（#573）。
    mgmt_file = find_mgmt_file_for_path(source_path, repo_root, index)

    if mgmt_file is None:
        mgmt_file = mgmt_path_for_file(source_path, repo_root)
        created_note = ""

        if mgmt_file.exists():
            # このソースパスの管理ファイルは存在しない（走査で見つからなかった）
            # のに導出先が埋まっている ＝ 別のソースパスの管理ファイルがそこに
            # ある（例: 拡張子を含まない旧命名で登録された "raw/paper.pdf" の
            # 管理ファイル "raw/paper.md" があるところへ、拡張子なしの実ファイル
            # "raw/paper" を登録した場合）。既存ファイルを書き換えず、ハッシュ
            # 接尾辞付きの代替パスへ退避して、その旨をメッセージに明示する（#573）。
            fallback_suffix = _path_hash_suffix(source_path)
            mgmt_file = mgmt_file.with_name(
                f"{mgmt_file.stem}-{fallback_suffix}{mgmt_file.suffix}"
            )
            created_note = (
                "derived filename was already taken by a different source path; "
                "used a hash-suffixed path instead"
            )

        mgmt_file.parent.mkdir(parents=True, exist_ok=True)
        mgmt_file.write_text(
            build_frontmatter_file(source_path, file_hash, license_override), encoding="utf-8"
        )
        if license_override and is_share_alike(license_override):
            # URL 側と同じ一度きりの通知（#570）。type: path には既知ドメイン対応表が
            # 効かないため入口は --license だけだが、義務の中身は URL ソースと変わらない。
            created_note = append_note(
                created_note,
                f"{license_override} is a share-alike license: a page written from this source "
                f"alone must be offered under it too",
            )
        if index is not None:
            # Keep a caller-supplied index in step with what was just written,
            # so a later source in the same run still resolves to this file.
            index.setdefault(source_path, mgmt_file)
        return ("CREATED", str(mgmt_file.relative_to(repo_root)), created_note)

    existing = mgmt_file.read_text(encoding="utf-8-sig")
    existing_hash = parse_frontmatter_hash(existing)
    existing_status = parse_frontmatter_status(existing)

    mgmt_rel = str(mgmt_file.relative_to(repo_root))

    # 取り下げ済み（Issue #737）— hash 比較より前に返す。ここを通すと
    # 「ソースファイルを1バイト触っただけで status: outdated に書き換わり、
    # Pass 1 の収集対象へ復帰する」という、取り下げの無言解除が成立する
    # （check_ingest_freshness.py が retracted を対象外にしているのと同じ理由）。
    if existing_status == "retracted":
        return retracted_result(mgmt_rel, existing)

    if existing_hash == file_hash:
        # ハッシュ一致 → outdated 状態なら pending に戻す（ソースが元に戻ったため）
        if existing_status == "outdated":
            mgmt_file.write_text(update_frontmatter_status(existing, "pending"), encoding="utf-8")
            return ("UPDATED", mgmt_rel, "hash unchanged, status: outdated → pending")
        return ("SKIP", mgmt_rel, "hash unchanged")

    # 既に outdated → hash は保持（前回生成時の参照点として機能する）
    if existing_status == "outdated":
        return ("SKIP", mgmt_rel, "already outdated, source changed again")

    # pending / generated / partial / failed → status のみ outdated に遷移（hash は保持）
    mgmt_file.write_text(update_frontmatter_status(existing, "outdated"), encoding="utf-8")
    return ("UPDATED", mgmt_rel, "hash mismatch, status: outdated")


def process_url(url: str, repo_root: Path, license_override: str = "") -> tuple[str, str, str]:
    """
    URL ソースを処理して管理ファイルを生成する。

    URL ソースは hash を空文字列で作成する（URL ハッシュの更新は再実行で行う設計）。
    既存の管理ファイルがあり status が pending/outdated なら SKIP する
    （次に Pass 1 が処理するキューに既に入っている）。status が
    generated/failed/excluded（前回の処理が完結済み）の場合は RECHECK を返す — このソースは Pass 1 が実際に再フェッチして
    ハッシュ比較するまで「変更されたかどうか」が判定不能なため（#310。管理ファイルの
    status/hash はここでは書き換えない — 再フェッチの結果 HASH_MATCH なら前回の状態の
    ままにしておく必要があるため）。

    partial は failed_pages で分かれる（#567）。非空なら再試行の余地があり Pass 1 の
    収集対象に残っているので SKIP。空なら同じ条件では二度と進展しないため収集対象から
    外れており、「キューに入っている」という SKIP の前提が成り立たない — この場合に
    SKIP を返すと、その URL は鮮度を再確認する経路をどこにも持たなくなるので
    generated 等と同じく RECHECK を返す。

    retracted（Issue #737）は上のどれにも落とさず RETRACTED を返す。再フェッチしても
    再登録しても取り下げの判断は変わらないため、伝えるべきなのは「なぜ使えないのか」
    だけである。
    """
    # 同一性はファイル名ではなく source.url で判定する（#572）。
    mgmt_file = find_mgmt_file_for_url(url, repo_root)
    created_note = ""

    if mgmt_file is None:
        try:
            mgmt_file = mgmt_path_for_url(url, repo_root)
        except ValueError as e:
            print(f"ERROR: {url}: {e}", file=sys.stderr)
            return ("ERROR", url, "")

        if mgmt_file.exists():
            # この URL の管理ファイルは存在しない（走査で見つからなかった）のに
            # 導出先が埋まっている ＝ 別の URL がサニタイズ・切り詰めの結果として
            # 同じ名前に解決された。黙って上書き・共有せず、ハッシュ接尾辞付きの
            # 代替パスへ退避し、退避したことをメッセージに明示する（#572）。
            fallback_suffix = _url_hash_suffix(normalize_url_for_identity(url))
            mgmt_file = mgmt_file.with_name(
                f"{mgmt_file.stem}-{fallback_suffix}{mgmt_file.suffix}"
            )
            created_note = (
                "derived filename was already taken by a different URL; "
                "used a hash-suffixed path instead"
            )

        mgmt_file.parent.mkdir(parents=True, exist_ok=True)
        # 明示指定 > 既知ドメイン対応表 > 空欄（#558）。空欄は「不明」であって
        # 「制約なし」ではない — 表示側も空欄のライセンスは何も主張しない。
        license_id = license_override or license_for_url(url)
        mgmt_file.write_text(build_frontmatter_url(url, license_id), encoding="utf-8")
        if license_id and not license_override:
            created_note = append_note(
                created_note, f"license: {license_id} (from the known-domain table)"
            )
        if license_id and is_share_alike(license_id):
            # ページがこのソース「だけ」から作られると、そのページは同じ
            # ライセンスでの提供義務を負う（#570）。登録時に一度だけ知らせる。
            created_note = append_note(
                created_note,
                f"{license_id} is a share-alike license: a page written from this source alone "
                f"must be offered under it too",
            )
        partial_note = partial_extraction_note(url)
        if partial_note:
            # 取得は成功するが一部が黙って落ちる URL 形（#715）。ブロックはせず、
            # ShareAlike と同じく登録時に一度だけ知らせて判断は人間に委ねる。
            created_note = append_note(created_note, f"partial extraction: {partial_note}")
        return ("CREATED", str(mgmt_file.relative_to(repo_root)), created_note)

    mgmt_rel = str(mgmt_file.relative_to(repo_root))
    existing = mgmt_file.read_text(encoding="utf-8-sig")
    existing_status = parse_frontmatter_status(existing)

    # 取り下げ済み（Issue #737）— RECHECK / SKIP のどちらにも落とさない。
    # RECHECK なら Pass 1 が取り下げたはずの URL を再フェッチしてしまい、
    # SKIP なら「既に登録済み」としか言われず理由が伝わらない。
    if existing_status == "retracted":
        return retracted_result(mgmt_rel, existing)

    if existing_status in ("generated", "failed", "excluded"):
        return ("RECHECK", mgmt_rel, f"previous status: {existing_status}")

    if existing_status == "partial" and not parse_frontmatter_has_failed_pages(existing):
        return (
            "RECHECK",
            mgmt_rel,
            "previous status: partial (no failed pages — not queued for reprocessing)",
        )

    return ("SKIP", mgmt_rel, "already registered")


def write_hash(mgmt_rel: str, content_file: str, repo_root: Path) -> tuple[str, str, str]:
    """
    フェッチ済みコンテンツ（--content-file）の SHA-256 を計算し、管理ファイルの
    source.hash に書き込む（type: url / type: wikicommit 向け）。

    WebFetch 自体はエージェントに委ねつつ、「計算して正しい書式で書き戻す」という
    決定論的な部分だけをスクリプトに切り出す（Issue #157 のスクリプト委譲パターン）。

    Returns:
        (result_code, mgmt_path_str, message)
        result_code: "HASH_WRITTEN" | "ERROR"
    """
    mgmt_path = repo_root / mgmt_rel
    if not mgmt_path.is_file():
        return ("ERROR", mgmt_rel, "the management file does not exist")

    content_path = Path(content_file)
    if not content_path.is_absolute():
        content_path = repo_root / content_path
    if not content_path.is_file():
        return ("ERROR", mgmt_rel, f"the content file does not exist: {content_file}")

    existing = mgmt_path.read_text(encoding="utf-8-sig")
    source_type = parse_frontmatter_source_type(existing)
    if source_type not in ("url", "wikicommit"):
        return (
            "ERROR",
            mgmt_rel,
            f"source.type is not url/wikicommit (currently: {source_type})",
        )

    new_hash = sha256_file(str(content_path))
    updated = update_frontmatter_hash(existing, new_hash)
    if parse_frontmatter_hash(updated) != new_hash:
        return (
            "ERROR",
            mgmt_rel,
            "the hash field was not found, so it could not be written (check the frontmatter format)",
        )
    mgmt_path.write_text(updated, encoding="utf-8")
    return ("HASH_WRITTEN", mgmt_rel, new_hash)


def check_hash(mgmt_rel: str, content_file: str, repo_root: Path) -> tuple[str, str, str]:
    """
    キャッシュ済みスクラッチファイル（--content-file）の SHA-256 が、管理ファイルの
    現在の source.hash と一致するか確認する（type: url / type: wikicommit 向け）。

    一致すれば Pass 1 は markitdown の再フェッチ・write_hash をスキップし、
    スクラッチファイルの内容をそのまま抽出テキストとして再利用できる（Issue #278）。
    read-only（write_hash と異なり管理ファイルは変更しない）。

    Returns:
        (result_code, mgmt_path_str, message)
        result_code: "HASH_MATCH" | "HASH_MISMATCH" | "ERROR"
    """
    mgmt_path = repo_root / mgmt_rel
    if not mgmt_path.is_file():
        return ("ERROR", mgmt_rel, "the management file does not exist")

    content_path = Path(content_file)
    if not content_path.is_absolute():
        content_path = repo_root / content_path
    if not content_path.is_file():
        return ("HASH_MISMATCH", mgmt_rel, "the scratch file does not exist (not cached)")

    existing = mgmt_path.read_text(encoding="utf-8-sig")
    source_type = parse_frontmatter_source_type(existing)
    if source_type not in ("url", "wikicommit"):
        return (
            "ERROR",
            mgmt_rel,
            f"source.type is not url/wikicommit (currently: {source_type})",
        )

    current_hash = parse_frontmatter_hash(existing)
    if not current_hash or current_hash == '""':
        return ("HASH_MISMATCH", mgmt_rel, "source.hash is not set")

    scratch_hash = sha256_file(str(content_path))
    if scratch_hash == current_hash:
        return ("HASH_MATCH", mgmt_rel, scratch_hash)
    return ("HASH_MISMATCH", mgmt_rel, "hash mismatch (the source changed and needs re-fetching)")


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
        print(f"CREATED: {path}" + (f" ({msg})" if msg else ""))
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
    elif result == "RETRACTED":
        print(f"RETRACTED: {path} ({msg})")
        counts["retracted"] += 1
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
        "--license",
        default="",
        help="SPDX-style license identifier to record as source.license on newly created "
        "management files (e.g. 'CC-BY-SA-4.0'). Overrides the known-domain table. Existing "
        "management files are never rewritten — edit them directly instead (Issue #558).",
    )
    parser.add_argument(
        "--license-for-url",
        metavar="URL",
        help="Look up URL's host in the known-domain license table and print the result, without "
        "registering anything (read-only). Lets wikicommit-collect show the same deterministic "
        "license on a candidate that registration would record on it (Issue #646). Ignores the "
        "positional 'source' argument.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()

    # Read-only lookup: the same table registration uses, one step earlier
    # (Issue #646). wikicommit-collect calls this so its candidate list can show
    # the license a candidate would be registered with — and, for ShareAlike, the
    # obligation the resulting page would inherit — while the human can still
    # decline. Registration already warns (Issue #570); by then the source is in.
    #
    # Always exits 0. "Not in the table" is not an error, and must not read as
    # "unrestricted" — the table holds only licenses a site states for its own
    # content as a whole, so the absence of an entry means WikiCommit does not
    # know, which is exactly what UNKNOWN says.
    if args.license_for_url:
        try:
            license_id = license_for_url(args.license_for_url)
        except ValueError:
            # urlsplit() rejects some malformed URLs outright (an unbalanced "["
            # raises "Invalid IPv6 URL"). Report that as UNKNOWN rather than a
            # traceback: this mode promises exit 0 and the caller's three
            # documented outcomes have no branch for a crash. A host that cannot
            # even be parsed is a host the table cannot hold, which is exactly
            # what UNKNOWN says. Callers do reach this — wikicommit-collect mines
            # candidate URLs verbatim out of third-party reference lists.
            license_id = ""
        if not license_id:
            print(f"UNKNOWN: {args.license_for_url}")
        elif is_share_alike(license_id):
            print(f"LICENSE: {license_id} (share-alike)")
        else:
            print(f"LICENSE: {license_id}")
        return 0

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
            "ERROR: source is required unless "
            "--write-hash/--check-hash/--fetch-url/--license-for-url is given",
            file=sys.stderr,
        )
        return 1
    counts: dict = {"created": 0, "updated": 0, "skipped": 0, "rechecked": 0, "retracted": 0}
    has_error = False

    if source.startswith("https://") or source.startswith("http://"):
        result, path, msg = process_url(source, repo_root, args.license)
        has_error = _tally(result, path, msg, counts)
    elif args.include:
        source_dir = Path(source)
        if not (repo_root / source_dir).is_dir():
            print(f"ERROR: {source}: directory does not exist", file=sys.stderr)
            return 1
        pattern = str(repo_root / source_dir / args.include)
        matched = [p for p in glob.glob(pattern, recursive=True) if Path(p).is_file()]
        if not matched:
            print(f"WARNING: {source}/{args.include}: no file matched", file=sys.stderr)
        # One scan of .wikicommit/source/path/ for the whole batch, kept up to
        # date by process_file() as it creates files; scanning per source would
        # read every management file once per matched source.
        index = build_source_path_index(repo_root)
        for abs_path in sorted(matched):
            # .as_posix() (not str()) so Windows callers get forward slashes
            # here too, matching process_file()'s own normalization (#269).
            rel_path = Path(abs_path).relative_to(repo_root).as_posix()
            result, path, msg = process_file(rel_path, repo_root, index, args.license)
            if _tally(result, path, msg, counts):
                has_error = True
    else:
        result, path, msg = process_file(source, repo_root, None, args.license)
        has_error = _tally(result, path, msg, counts)

    c, u, s, r = counts["created"], counts["updated"], counts["skipped"], counts["rechecked"]
    rt = counts["retracted"]
    print(f"SUMMARY: created={c}, updated={u}, skipped={s}, rechecked={r}, retracted={rt}")
    return 1 if has_error else 0


def main() -> int:
    return main_from_args()


if __name__ == "__main__":
    sys.exit(main())
