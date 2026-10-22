#!/usr/bin/env python3
"""
add_source.py — ソース登録のスクリプト。wikicommit-generate Step 0 が主な呼び出し元で、
wikicommit-collect・wikicommit-ask・resolve_source_cache_path.py も `--fetch-url` 等を呼ぶ
（そのため Skill 内ではなく `.wikicommit/scripts/` に置く）。

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
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit

# type: url / type: wikicommit ソースの markitdown フェッチに使う User-Agent。
# 既定の python-requests UA は Wikimedia 系ドメイン（Wikipedia/Wikisource 等）に
# 403 Forbidden で拒否されるため、WikiCommit を名乗る独自 UA を送る。
USER_AGENT = "WikiCommit/1.0 (+https://github.com/wikicommit/wikicommit)"

# 取り込み元ドメイン → そのサイトが自サイトのコンテンツ全体に対して明示している
# ライセンスの SPDX 識別子。`KNOWN_JS_SHELL_DOMAINS`
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


# コピーレフト系ライセンスの識別子接頭辞。値は自由記述なので完全な判定は
# できないが、既知ドメイン対応表が返す値と SPDX の一般的な綴りは覆う。
#
# **ここに載るのはそのライセンスの性質であって、あるページが二次的著作物に当たるかの
# 判断ではない。** あるライセンスがコピーレフトかどうかはライセンス自身の事実であり、
# それを読んで書かれた散文の要約が義務を負うかは別の問いである。WikiCommit はその問いに
# 答えない（`is_share_alike()` の呼び出し側が出すのは通知であって拒否ではない）ので、
# 表の中で解こうとしないこと。
#
# 名前が「ShareAlike」なのは Creative Commons 由来の歴史的経緯で、中身はコピーレフト系
# 一般である。改名しないのは、`LICENSE: <id> (share-alike)` という出力が
# `wikicommit-collect` の SKILL.md に契約として書かれているため。
#
# **弱いコピーレフト（LGPL / MPL / EPL / CDDL）も一律で入れる**。
# ソフトウェアでは「及ぶ範囲が狭い」ことに意味があるが、リンク境界もファイル境界も
# 散文には対応物が無いので、その区別はここでは働かない。誤りの向きも非対称で、
# 足りなければ利用者は義務に気づかないまま公開し（取り返しがつかない側）、足しすぎても
# 注意書きが 1 行余計に出るだけである。ここに挙げた接頭辞はいずれも実際にコピーレフト
# なので、「誤った注意書き」にはならない。
#
# 接頭辞照合なので `AGPL-3.0` は `gpl` に前方一致せず `agpl` が別に要る。逆に
# `LGPL-3.0` も `gpl` では一致しないため、`lgpl` を落としても意図しない取りこぼしには
# ならない（落とすなら明示的な判断になる）。
#
# **末尾にハイフンを付けない**。SPDX 識別子は必ず付くので `gpl-` でも SPDX は覆えるが、
# この値は自由記述であり `GPLv3` や素の `GPL` は普通に書かれる綴りで、ハイフンを付けると
# そのどちらも落ちる。上の非対称（足りなければ気づかないまま公開する／足しすぎても 1 行
# 余計に出るだけ）はここにもそのまま当たる。`gpl` で始まる permissive なライセンスは
# 無いので広げすぎにもならず、既存の 5 つ（`cc-by-sa` 等）が元からハイフン無しなのとも
# 揃う。
SHARE_ALIKE_LICENSE_PREFIXES = (
    # Creative Commons ほか
    "cc-by-sa",
    "cc-sa",
    "cc-by-nc-sa",
    "gfdl",
    "odbl",
    # 強いコピーレフト
    "gpl",
    "agpl",
    "osl",
    "sspl",
    # 弱いコピーレフト（上記のとおり一律で入れる）
    "lgpl",
    "mpl",
    "epl",
    "cddl",
    # 以下 3 件とも本文の条項で確認済み（評判ではなく条項で判定するのがこの表の規律）。
    # `eupl` が巻き込む SPDX 識別子は `EUPL-1.0`/`1.1`/`1.2` の 3 件だけで、3 版とも
    # "Copyleft clause" を持つ（permissive な版は存在しない）。`EUPL-1.2` は
    # `Original Work` を "the work **or software**" と定義しており、行政文書を取り込む
    # Wiki が実際に当たりうる — この表で最もコードから遠い側の族である。
    "eupl",
    # `CPL-1.0` の 1 件だけに一致する（`CPAL-1.0` は `cpa` で始まるので巻き込まない）。
    # EPL に置き換えられた旧ライセンスであり新規採用はほぼ無いが、この表の規律は
    # 「確認済みのものだけを持つ」であって「よく使われるものだけを持つ」では
    # ないため、確認を経た以上は入れる。
    "cpl",
    # **`ms-` にしてはならない。** SPDX には `MS-PL`・`MS-LPL`・`MS-RL` の 3 つがあり、
    # reciprocal 条項を持つのは `MS-RL` だけである。族単位の接頭辞に揃えると permissive な
    # `MS-PL` を巻き込む — この表で唯一、族が permissive と copyleft に割れている箇所。
    "ms-rl",
)

# **CeCILL は意図的に入れていない。漏れではない。**
# 前方一致という実装の形が選択肢を縛る: `CeCILL`/`CeCILL-C` はコピーレフトだが
# `CeCILL-B` は帰属表示のみを求める permissive（§5.3.4。本文で確認済み）であり、
# `CeCILL-B` は `cecill` で始まるため「裸の `CeCILL` を拾う」と「`CeCILL-B` を拾わない」は
# 純粋な前方一致では両立しない。版ごとの列挙（`cecill-1`/`cecill-2`/`cecill-c`）は
# 裸の `CeCILL` を取りこぼし、末尾ハイフン無しの規約が守ろうとした自由記述の綴りを
# 1 族のために裏返すことになる。除外リストを持ち込む案は `is_share_alike()` を
# 前方一致だけでなくするため、`sources[].license` に CeCILL が現れる見込みに見合わない。
# したがって `CeCILL`/`CeCILL-C` の沈黙は残る。
#
# 既知の誤検知が 1 件ある: `mpl` は `mplus`（mplus Font License。permissive）にも
# 前方一致する。**直さない** — 誤りの向きが上の非対称の意図した側（注意書きが 1 行余計に
# 出るだけ）であり、ここに書いておくのは次にこの表を見た人が欠陥として起票し直さない
# ためと、「足しすぎの劣化は 1 行で済む」が仮定ではなく実例を持つことを残すためである。


# 静的取得で「本文は取れるが、ページが載せている内容の一部が黙って落ちる」ことが
# 確認済みの URL 形。値は「何が落ちるか」の一文で、登録時に一度だけ知らせる
# ためだけに使う（`is_share_alike()` の注意書きと同じ形）。
#
# これは**ガードではない** — ブロックせず、`status` も変えず、取得も止めない。
# `check_extraction_quality.py` の 3 ガードはいずれも「そもそも取得できるか／取れた
# ものがゴミか」を判定して Pass 1 の分岐を左右するが、ここで扱うのは「取得は成功し、
# 取れた本文も本物で、ただし別の一部が欠ける」という、取得後のテキストからは原理的に
# 見分けられない partial extraction（YouTube の字幕が黙って落ちるのと同じ失敗クラス）
# である。本文だけで十分なソースは実在するため、止めるのではなく知らせる。
#
# 判定はホストとパスの形だけで決まる決定論的なもので、`KNOWN_SOURCE_LICENSES` と同じ
# 「確認済みのものだけを表に持つ」パターンに従う。ただし `KNOWN_JS_SHELL_DOMAINS` の
# 「確認済みのみ」規則をそのまま持ち込みはしない — あちらは誤ったエントリが取得自体を
# 飛ばす（実害がある）のに対し、こちらの誤りは余計な注意書きが 1 行出るだけであり、
# 取りこぼしの方（黙った欠落）が明確に重い。非対称の向きが逆なので、規則も同じには
# ならない。
_GITHUB_THREAD_PATH_RE = re.compile(r"^/[^/]+/[^/]+/(?:issues|pull)/\d+(?:/|$)")

# arXiv の `/abs/<id>` はランディングページ（タイトル・著者・アブストラクト・投稿履歴）
# で、論文本体は含まれない。`<id>` は `/abs/` より後ろ全部 — 旧形式の ID は
# `hep-th/9901001` のようにスラッシュを含むので、最初のスラッシュで切らない。
_ARXIV_ABS_PATH_RE = re.compile(r"^/abs/(?P<id>[^/].*?)/*$")
_ARXIV_VERSION_RE = re.compile(r"v\d+$")


def arxiv_abs_id(url: str) -> str:
    """URL が arXiv の `/abs/<id>` 形なら `<id>` を返す。違えば空文字列。

    ホストは `host_suffix_candidates()` で照合する（`export.arxiv.org` も対象）。
    """
    try:
        if "arxiv.org" not in host_suffix_candidates(url):
            return ""
        m = _ARXIV_ABS_PATH_RE.match(urlsplit(url).path or "/")
    except ValueError:
        return ""
    return m.group("id") if m else ""


def arxiv_fulltext_urls(paper_id: str) -> tuple[str, str]:
    """arXiv の論文 ID から本文の URL（`/html/` と `/pdf/`）を組み立てる。"""
    return (f"https://arxiv.org/html/{paper_id}", f"https://arxiv.org/pdf/{paper_id}")


def _arxiv_abs_note(match: re.Match) -> str:
    paper_id = match.group("id")
    html_url, pdf_url = arxiv_fulltext_urls(paper_id)
    note = (
        "only the abstract and bibliographic data are extracted — the paper's full text "
        f"is not on this page. To write from the paper itself, register {html_url} "
        f"instead (or {pdf_url} if that has no HTML version)"
    )
    if not _ARXIV_VERSION_RE.search(paper_id):
        note += (
            ". This URL has no version (e.g. v1), so it follows the latest revision and "
            "its content changes when the paper is revised — prefer a versioned URL"
        )
    return note


# ホスト（登録可能ドメイン相当の接尾辞）→ (パス判定, 何が落ちるか)。
# 「何が落ちるか」は文字列か、パスの一致（`re.Match`）を受けて文字列を返す関数
# （通知に URL から取り出した値を埋め込むとき。arXiv の `<id>`）。
PARTIAL_EXTRACTION_URL_NOTES = (
    (
        "github.com",
        _GITHUB_THREAD_PATH_RE,
        "only the issue/PR body is extracted — every comment on the thread is "
        "dropped without an error. Register this only if the body alone is the "
        "source you want",
    ),
    ("arxiv.org", _ARXIV_ABS_PATH_RE, _arxiv_abs_note),
)


def url_host(url: str) -> str:
    """URL のホスト（小文字・userinfo とポートを除く）。ホストを引く箇所はすべてこれを共有する。"""
    return urlsplit(url).netloc.lower().split("@")[-1].split(":")[0]


def host_suffix_candidates(url: str) -> list[str]:
    """URL のホストを、左ラベルを順に落とした接尾辞の列（具体的な順）で返す。

    `it.wikipedia.org` → `["it.wikipedia.org", "wikipedia.org"]`。末尾 1 ラベル
    （TLD 単独）は含めない。ホスト表を引く箇所（`license_for_url()` /
    `partial_extraction_note()`）はすべてこれを共有する — 同じ導出を各所に複製
    すると、片方だけホスト解析の端ケースを直したときに黙ってずれるため。
    """
    host = url_host(url)
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
        if domain not in candidates:
            continue
        match = path_re.search(path)
        if match:
            return note(match) if callable(note) else note
    return ""


# 取得元の差し替え表。画面の取得結果に、本文と無関係に毎回変わる行（スター数・
# コミット数・ファイル一覧の最終コミット等）が入るため、`source.hash` が本文の変化を
# 表さなくなる URL の形について、画面の代わりに取得する URL の候補を引く。
#
# 差し替えは取得結果そのものを差し替える — hash を取るためだけの抽出にはしない。
# `source.hash` ＝ スクラッチファイルの SHA-256 という不変条件を保ち、`--check-hash`
# 等の照合側を変えずに済ませるため。候補は順に試し、最初に取れたものを書く。
# 全候補が 404 のとき（差し替え先が存在しない）だけ元の URL の取得に戻る。それ以外の
# 失敗では戻らない — 戻ると、取れた経路によって同じソースの hash の意味が変わる。
#
# ホストは完全一致で照合する（`host_suffix_candidates()` は使わない —
# `docs.github.com`・`gist.github.com` を巻き込むため）。

# `github.com/<owner>/<repo>` だけ（末尾の `/`・`.git` は許す）。2 区画でもリポジトリで
# ない GitHub 自身のページは除く — 外さなくても全候補が 404 で元の取得に戻るが、
# 余計な取得を毎回するため。
_GITHUB_REPO_TOP_RE = re.compile(r"^/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$")
_GITHUB_NON_REPO_OWNERS = frozenset(
    {
        "about", "account", "apps", "codespaces", "collections", "customer-stories",
        "enterprise", "events", "explore", "features", "login", "marketplace",
        "notifications", "organizations", "orgs", "pricing", "readme", "security",
        "settings", "site", "solutions", "sponsors", "topics", "trending", "users",
    }
)
# README の候補。順序は固定（同じリポジトリでは常に同じファイルを取るため）。
# `HEAD` は raw.githubusercontent.com で既定ブランチに解決される。
_GITHUB_README_NAMES = (
    "README.md", "README.markdown", "README.rst", "README.txt", "README",
    "readme.md", "Readme.md", "README.MD",
)
_GITHUB_README_DIRS = ("", ".github/", "docs/")


def _github_readme_urls(match: re.Match) -> list[str]:
    owner, repo = match.group("owner"), match.group("repo")
    if owner.lower() in _GITHUB_NON_REPO_OWNERS:
        return []
    return [
        f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{d}{name}"
        for d in _GITHUB_README_DIRS
        for name in _GITHUB_README_NAMES
    ]


# (ホスト, パス判定, 候補の URL を返す関数, 取得元の名前)
FETCH_SOURCE_OVERRIDES = (
    (
        frozenset({"github.com", "www.github.com"}),
        _GITHUB_REPO_TOP_RE,
        _github_readme_urls,
        "the repository's README (raw)",
    ),
)


def fetch_source_override(url: str) -> tuple[list[str], str]:
    """取得元の差し替え表を引く。当たれば (候補の URL の列, 取得元の名前)、無ければ ([], "")。"""
    try:
        host = url_host(url)
        path = urlsplit(url).path or "/"
    except ValueError:
        return ([], "")
    for hosts, path_re, candidates, label in FETCH_SOURCE_OVERRIDES:
        if host not in hosts:
            continue
        match = path_re.match(path)
        if match:
            urls = candidates(match)
            if urls:
                return (urls, label)
    return ([], "")


def is_share_alike(license_id: str) -> bool:
    """ライセンス識別子がコピーレフト系かどうかを返す。

    返すのはライセンスの性質だけである。そのソースから書かれたページが義務を負うか
    どうかは判断しない（表の上のコメント参照）。
    """
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
    utf-8-sig に統一しているのと同じ問題。管理ファイルの読み書きは行単位の自前
    パースで行っており、`_frontmatter.py` の dict 化とは別の処理なので方針だけを
    踏襲する）。同一性走査でこれが起きると、既存の管理ファイル
    が見つからないまま「導出先が別ソースに占有されている」と誤判定され、同じ
    ソースに対する2つ目の管理ファイルが作られてしまう。
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


# Query parameters that identify *how a reader arrived at* a URL rather than
# *which document it is*. They are dropped before a URL is turned into a
# filename or compared for identity, so that the same article shared
# through two different campaigns still resolves to one management file. The
# denylist is inherently incomplete; a parameter it misses costs a second
# management file for the same document, never a wrong source (the failure
# mode that identity-by-URL exists to prevent).
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
# non-ASCII path segments that cost up to 4 bytes each.
_MAX_STEM_BYTES = 200

# Length of the SHA-256 prefix appended to a derived filename when it has to be
# truncated or moved aside because a different source already occupies
# that name (URLs and paths alike).
_HASH_SUFFIX_LEN = 8


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_PARAMS or lowered.startswith(_TRACKING_PARAM_PREFIXES)


def normalize_url_for_identity(url: str) -> str:
    """Return the form of a URL used for filename derivation and identity.

    Two URLs that normalize to the same string are treated as the same source.
    This is used *only* internally: the ``source.url`` frontmatter field always
    records the URL exactly as the user supplied it, so provenance stays
    verbatim.

    Normalization drops the fragment (never sent to a server, so it cannot
    select different content), drops tracking parameters, and sorts the
    remaining query parameters so that reordering them doesn't create a second
    source. Host and path are deliberately left alone — treating
    ``youtu.be/<id>`` and ``youtube.com/watch?v=<id>`` as one source needs
    site-specific knowledge and is deliberately out of scope here.
    """
    url = url.split("#", 1)[0]
    base, sep, query = url.partition("?")
    # Strip trailing slashes from the path only. Doing it to the whole string
    # would turn a hostless "https://" into "https:", which url_to_filename
    # would then sanitize into a bogus host instead of rejecting.
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
    instead of flattening every URL into one directory.

    A bare-domain URL (no path segment, e.g. "https://example.com") returns
    just the host, with no "/index" suffix. A real "/index" path (e.g.
    "https://example.com/index") sanitizes to the same "index" stem that an
    "/index" fallback would use, so a fixed fallback name would make the two
    distinct URLs collide on the same management file path. Returning
    the bare host instead places the bare-domain management file as
    ".wikicommit/source/url/<host>.md", a sibling of the "<host>/" directory
    that holds paths — a name no sanitized real path can ever produce, since
    every real path lives one level deeper under "<host>/".

    The query string is kept, because many sites identify a document only by
    a query parameter — without it every "https://www.youtube.com/watch?v=<id>"
    would collapse onto the same "watch" stem, and registering a second video
    would silently report success against the first video's management file.
    The query is normalized first (see normalize_url_for_identity) so tracking
    parameters and parameter order don't split one document across two files,
    then folded into the stem: "watch?v=abc" → "watch-v-abc".

    Management files whose name was derived by an older rule keep that name —
    there is no automatic migration, and none is needed: process_url()
    identifies an existing source by scanning for a matching source.url rather
    than by recomputing this name.
    """
    normalized = normalize_url_for_identity(url)
    url = re.sub(r"^https?://", "", normalized)
    url = url.rstrip("/")
    # Decode only non-ASCII percent-encoded byte runs (%80-%FF) so CJK/etc.
    # path segments stay readable instead of turning into hex litter. ASCII
    # percent-encoding (e.g. %2F) is left encoded so it can't collapse onto a
    # literal separator once "/" becomes "-" below (would otherwise alias
    # "foo%2Fbar" and "foo/bar" to the same filename).
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
        # docstring for why this must not be "{host}/index". A bare
        # domain carrying only a query (e.g. "https://example.com?p=1") also
        # lands here, with the query already folded into the host half by
        # partition("/") ("example.com-p-1"), so it still keeps its own stem
        # as a sibling of the "<host>/" directory. That stem needs the same
        # length guard as the path branch below — without it a long query on a
        # bare domain produces a name past the filesystem's 255-byte limit and
        # surfaces as an OSError instead of a usable file.
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
        # Readability is sacrificed, but the source.url frontmatter
        # field still records the URL in full.
        path = _truncate_stem(path, _url_hash_suffix(normalized))
    return f"{host}/{path}"


def mgmt_path_for_file(source_path: str, repo_root: Path) -> Path:
    """ファイルソースの管理ファイルパスを計算する。

    元の拡張子は捨てずに保持し、".md" を付け足す（"raw/paper.pdf" →
    ".wikicommit/source/path/raw/paper.pdf.md"）。拡張子を置き換える
    （`with_suffix(".md")`）と "raw/paper.pdf" と "raw/paper.docx" が同じ管理
    ファイルに解決され、後から登録した方が既存ソースを status: outdated に誤って
    書き換える。付け足す方式では管理ファイルパスがソースパスと1対1に対応するため、
    この衝突が構造的に起こらない。

    Note: 拡張子なしの旧名で登録された管理ファイルはそのまま残る — 自動移行は
    しない。process_file() は導出名ではなく source.path の走査で既存管理ファイルを
    特定するため、旧名のままでも二重登録にならない。
    """
    rel = PurePosixPath(normalize_source_path(source_path))
    name = f"{rel.name}.md"
    if len(name.encode("utf-8")) > _MAX_STEM_BYTES:
        # Appending ".md" (rather than replacing the extension) makes the
        # derived name 3 bytes longer than the source filename, so a source
        # file whose own name is already at the filesystem's 255-byte limit
        # would fail the write with a bare OSError. Truncate and disambiguate
        # with a hash of the source path, exactly as url_to_filename() does for
        # over-long URL stems; identity does not depend on this name being
        # reconstructible (it is matched by source.path), so the truncation is
        # safe.
        name = f"{_truncate_stem(rel.name, _path_hash_suffix(str(rel)))}.md"
    return repo_root / ".wikicommit" / "source" / "path" / rel.parent / name


def _resolves_inside(path: Path, repo_root: Path) -> bool:
    """Whether `path`, symlinks followed, lies under `repo_root` — the same
    test `validate_frontmatter.py` and `resolve_source_cache_path.py --obtain`
    apply to `sources[].path`, so a source registered here is never one the
    page citing it cannot carry."""
    try:
        return path.resolve().is_relative_to(repo_root.resolve())
    except (OSError, RuntimeError):
        return False


def normalize_source_path(source_path: str) -> str:
    """`source.path` の同一性比較に使う正規形を返す。

    Windows ネイティブの呼び出し元が渡すバックスラッシュ区切りと、
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

    同一性キーは導出ファイル名ではなく `source.path` そのものとする（`type: url`
    側の `source.url` と同じ柱）。導出名を同一性キーに使うと、導出名が衝突する
    別ファイルを登録したときに既存の管理ファイルがハッシュ不一致経路に入り、
    登録したはずのファイルはどこにも記録されないまま無関係な既存ソースが
    status: outdated に書き換えられる。

    実ファイルを走査するため、拡張子を含まない旧命名の管理ファイルも自動移行
    なしでヒットする。
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
    process_file() normalizing path separators to forward slashes.
    """
    return "'" + value.replace("'", "''") + "'"


def _license_line(license_id: str) -> str:
    """`source.license` の行を組み立てる（未知なら値なしの空欄で書き出す）。"""
    return f"  license: {_yaml_single_quote(license_id)}" if license_id else "  license:"


# `source.lang` は登録時には常に空で置く。値を書くのは抽出テキストを
# 全文読む wikicommit-generate の Pass 2a だけであり、ここでは言語を知らない。
# 空のキーを雛形に置くのは、管理ファイルを開いた人にフィールドの存在を伝えるためと、
# Pass 2a が「既存の行を埋める」だけで済むようにするため。消費者（俯瞰ページの
# ソース言語別集計）は既に配られているので、消費者の無い受け皿だけを配る形には
# 当たらない。
_LANG_LINE = "  lang:"


def build_frontmatter_file(source_path: str, file_hash: str, license_id: str = "") -> str:
    return f"""---
source:
  type: path
  path: {_yaml_single_quote(source_path)}
  hash: {file_hash}
{_license_line(license_id)}
{_LANG_LINE}

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
{_LANG_LINE}

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


def parse_frontmatter_license(content: str) -> str:
    """管理ファイルの frontmatter から source.license の値を抽出する（空欄なら ""）。"""
    start, end = _frontmatter_slice(content)
    m = re.search(r"^\s+license:[ \t]*(.*)$", content[start:end], re.MULTILINE)
    if not m:
        return ""
    value = m.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        value = value[1:-1].replace("''", "'")
    return value


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
    """管理ファイルの `## Retraction Reason` セクション本文を1行に畳んで返す。

    `status: retracted` は人間にしか書けない値であり（証拠拘束ルールの下で機械は
    ソースを疑えない）、なぜ取り下げたかは enum ではなく散文で残す — 機械は報告
    しかせず、理由で分岐する消費者がいないため（`## Failure Reason` と同じ形）。

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

    `SKIP` に落とさないことが要点である。`SKIP: already registered` は「なぜ
    使えないのか」を一切伝えないため、人間が同じソースをもう一度登録しようと
    したときに取り下げの事実が黙って握り潰される。
    """
    reason = parse_retraction_reason(content)
    detail = f"reason: {reason}" if reason else "no ## Retraction Reason recorded"
    return ("RETRACTED", mgmt_rel, f"previously retracted by a human — {detail}")


def parse_frontmatter_has_failed_pages(content: str) -> bool:
    """管理ファイルの failed_pages が非空かどうかを返す。

    `partial` が「再試行に意味がある（生成失敗を含む）」のか、そうでないのかを
    分ける唯一の手がかり。前者だけが引数なし実行の収集対象に残る。後者は現在
    `ambiguous: true` の型確定待ちだけである（読み直しても同じ ambiguous が返る）。
    ポリシー除外のみのソースは Pass 4 が `generated` にするが、古い管理ファイルでは
    `partial` のまま残っていることがあり、同じく後者として扱う。

    フロー形式（`failed_pages: []` / `[a, b]`）とブロック形式（次行以降の
    `  - ...`）の両方を読む。Pass 4 が書くのは前者だが、人間が手で編集した
    ファイルは後者になりうる。値が読めなければ False を返す — 判定できない
    ものを「再試行の余地あり」と見なすと、進展しないファイルが枠を占め続ける
    ため、安全側は False。
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

    同一性キーは導出ファイル名ではなく `source.url` そのものとする。
    導出名を同一性キーに使うと、異なる URL がたまたま同じ名前に解決された場合に
    「登録済み」と誤判定し、しかも status が generated/failed/excluded なら
    RECHECK として *別の URL* を再フェッチしてしまう（silent wrong-source）。

    実ファイルを走査するため、旧フラット命名・パーセントエンコードのままの命名・
    クエリを落として作られた管理ファイルのいずれも自動移行なしでヒットする
    （`resolve_source_cache_path.py` が参照側で採っている方式と同じ）。走査コストは
    URL ソース件数に対して線形だが、登録時の1回きりで実用上問題にならない。
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
    # consistent regardless of the caller's OS.
    # The same normalization is what identity comparison uses, so
    # applying it up front keeps the stored source.path, the derived
    # management-file path, and the lookup key in agreement.
    source_path = normalize_source_path(source_path)

    abs_source = repo_root / source_path
    if Path(source_path).is_absolute():
        err = f"ERROR: {source_path}: absolute paths are not accepted; give a path relative to the repository root"
    elif not _resolves_inside(abs_source, repo_root):
        # `..` or a symlink pointing out: validate_frontmatter.py rejects the
        # page that would cite it, and review / fix refuse to read it.
        err = f"ERROR: {source_path}: resolves outside the repository"
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

    # 同一性はファイル名ではなく source.path で判定する。
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
            # 接尾辞付きの代替パスへ退避して、その旨をメッセージに明示する。
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
            # URL 側と同じ一度きりの通知。type: path には既知ドメイン対応表が
            # 効かないため入口は --license だけだが、義務の中身は URL ソースと変わらない。
            created_note = append_note(
                created_note,
                f"{license_override} is a copyleft license: a page written from this source "
                f"alone may have to be offered under it too — check before publishing",
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

    # 取り下げ済み — hash 比較より前に返す。ここを通すと
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
    ハッシュ比較するまで「変更されたかどうか」が判定不能なため（管理ファイルの
    status/hash はここでは書き換えない — 再フェッチの結果 HASH_MATCH なら前回の状態の
    ままにしておく必要があるため）。

    partial は failed_pages で分かれる。非空なら再試行の余地があり Pass 1 の
    収集対象に残っているので SKIP。空なら（型確定待ちの ambiguous。古い管理ファイル
    ではポリシー除外のみのものも）読み直しても進展しないため収集対象から
    外れており、「キューに入っている」という SKIP の前提が成り立たない — この場合に
    SKIP を返すと、その URL は鮮度を再確認する経路をどこにも持たなくなるので
    generated 等と同じく RECHECK を返す。

    retracted は上のどれにも落とさず RETRACTED を返す。再フェッチしても
    再登録しても取り下げの判断は変わらないため、伝えるべきなのは「なぜ使えないのか」
    だけである。
    """
    # 同一性はファイル名ではなく source.url で判定する。
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
            # 代替パスへ退避し、退避したことをメッセージに明示する。
            fallback_suffix = _url_hash_suffix(normalize_url_for_identity(url))
            mgmt_file = mgmt_file.with_name(
                f"{mgmt_file.stem}-{fallback_suffix}{mgmt_file.suffix}"
            )
            created_note = (
                "derived filename was already taken by a different URL; "
                "used a hash-suffixed path instead"
            )

        mgmt_file.parent.mkdir(parents=True, exist_ok=True)
        # 明示指定 > 既知ドメイン対応表 > 空欄。空欄は「不明」であって
        # 「制約なし」ではない — 表示側も空欄のライセンスは何も主張しない。
        license_id = license_override or license_for_url(url)
        mgmt_file.write_text(build_frontmatter_url(url, license_id), encoding="utf-8")
        if license_id and not license_override:
            created_note = append_note(
                created_note, f"license: {license_id} (from the known-domain table)"
            )
        if license_id and is_share_alike(license_id):
            # ページがこのソース「だけ」から作られると、そのページは同じライセンスでの
            # 提供義務を負いうる。登録時に一度だけ知らせる。
            #
            # 「負いうる」と書き、断定しない。散文の要約が二次的著作物に当たるかは
            # 開いた問いであり、WikiCommit はそこに答えない。
            # 断定すると、答えていないことを答えたふりをすることになる。弱めても信号は
            # 落ちない — 利用者は「このソースはコピーレフトである」という事実を
            # 引き続き受け取る。
            created_note = append_note(
                created_note,
                f"{license_id} is a copyleft license: a page written from this source alone "
                f"may have to be offered under it too — check before publishing",
            )
        _override_urls, override_label = fetch_source_override(url)
        if override_label:
            # hash と生成に使うテキストが画面ではなくなることを、登録時に一度だけ知らせる。
            created_note = append_note(
                created_note, f"fetched as {override_label}, not the rendered page"
            )
        partial_note = partial_extraction_note(url)
        if partial_note:
            # 取得は成功するが一部が黙って落ちる URL 形。ブロックはせず、
            # ShareAlike と同じく登録時に一度だけ知らせて判断は人間に委ねる。
            created_note = append_note(created_note, f"partial extraction: {partial_note}")
        return ("CREATED", str(mgmt_file.relative_to(repo_root)), created_note)

    mgmt_rel = str(mgmt_file.relative_to(repo_root))
    existing = mgmt_file.read_text(encoding="utf-8-sig")
    existing_status = parse_frontmatter_status(existing)

    # 取り下げ済み — RECHECK / SKIP のどちらにも落とさない。
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
    決定論的な部分だけをスクリプトに切り出す（スクリプト委譲パターン）。

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
    スクラッチファイルの内容をそのまま抽出テキストとして再利用できる。
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


def extract_cache_path(mgmt_path: Path, repo_root: Path) -> Path | None:
    """`type: path` の抽出テキストキャッシュの置き場。

    `.wikicommit/.cache/extract-path/` ＋ 管理ファイルの `.wikicommit/source/path/`
    相対パスをそのまま使う。**末尾の `.md` を落として付け直さない** — 管理ファイル名は
    元の拡張子を保持して `.md` を付す形（`raw/paper.pdf.md`）なので、
    そのまま使えば `paper.pdf` と `paper.docx` が同じキャッシュへ解決する衝突が
    構造的に起こらない。`with_suffix(".md")` で付け直すとまさにその衝突が戻る。

    `type: url` 側の scratch（`.wikicommit/.cache/ingest-fetch/`）とディレクトリを
    分けるのは、両者を同じ木に置くと衝突しうるためである — URL 側の scratch path は
    `.wikicommit/source/url/` 相対なので、リポジトリに `example.com/article` という
    パスが実在すれば同じ位置を指す。既存の URL キャッシュを一斉失効させずに衝突を
    構造的に無くせる側を採った。

    `.wikicommit/source/path/` の外を指す管理ファイルには `None` を返す。実際に起こる
    のは `.wikicommit/ingest/path/` のままの管理ファイルが残る古いリポジトリで、
    `ingest/` から `source/` への改名は自動移行されない。導出だけを試みて例外を
    投げると、呼び出し側が `ERROR:` として報告する経路を通らずトレースバックで実行
    全体が落ちる — このキャッシュは最適化であり、ソースの処理を止める理由になっては
    ならない。
    """
    mgmt_root = repo_root / ".wikicommit" / "source" / "path"
    try:
        rel = mgmt_path.resolve().relative_to(mgmt_root.resolve())
    except ValueError:
        return None
    return repo_root / ".wikicommit" / ".cache" / "extract-path" / rel


def check_path_cache(mgmt_rel: str, repo_root: Path) -> tuple[str, str, str, str | None]:
    """`type: path` の抽出テキストキャッシュが今のファイルの版に対して有効か確認する。
    read-only。

    `type: url` の `--check-hash` と**判定の向きが違う**。あちらは `source.hash` が
    抽出テキストのハッシュなので、キャッシュ自身をハッシュして突き合わせられる。
    `type: path` の `source.hash` は**生ファイル**の SHA-256（`add_source.py` が登録時に
    計算し、`check_ingest_freshness.py` が現物と突き合わせる正本）なので、キャッシュを
    ハッシュしても比べる相手がいない。代わりに**生ファイル側で判定する**: 現在の
    ファイルの SHA-256 が `source.hash` と一致し、かつキャッシュが存在すれば、その
    キャッシュはその版の抽出結果であるとみなす。`check_ingest_freshness.py` が既に
    行っている比較そのものなので、新しいハッシュフィールドは要らない。

    **`source.hash` には一切触れない。** キャッシュファイルを `--content-file` として
    `--write-hash` に渡すと、意味の違うハッシュ（抽出テキスト）で生ファイルのハッシュを
    上書きしてしまい、`check_ingest_freshness.py` の鮮度判定が壊れる。

    残る限界は「抽出ツールの版が変わってもキャッシュは失効しない」ことだが、これは
    `type: url` 側とまったく同じ性質であり、新しく持ち込むものではない。

    **`.md` / `.txt` は `RAW` を返す（キャッシュを持たない）。拡張子はシンボリック
    リンクを辿った解決先のもので判定する**。`raw/notes.md` がリポジトリ内の
    PDF を指すとき、リンク名で判定すると generate の Pass 1 は PDF のバイトを `.md` として
    読み、review / fix（`resolve_source_cache_path.py --obtain`）は実体の PDF を
    抽出して照合する — 生成と照合が別のテキストを見る。判定をエージェントの拡張子の読みに
    任せず、`--obtain` と同じ規則でここに置く。`RAW` の 2 番目の値は読むファイル（解決先の
    リポジトリルート相対パス）。それ以外の拡張子のキャッシュの置き場は管理
    ファイル（リンク名）から決まり、`--obtain` も同じ位置を引くので、generate が書いた
    抽出結果に 2 回目以降の review / fix が当たる。抽出するファイル（解決先）は戻り値の
    4 番目で返す。

    **存在の判定とハッシュも解決先（`repo_root / target`）に対して行う**。
    範囲の検査・`RAW` の判定・存在・ハッシュ・`extract=` がすべて同じ 1 回の解決に
    拠るので、その間にリンクが張り替わっても、ハッシュを取ったファイルと抽出させる
    ファイルが食い違わない（`resolve_source_cache_path.py --obtain` も解決先をハッシュ
    する）。CLI は 4 番目をそのまま `extract=` に使い、管理ファイルを読み直さない。

    Returns:
        (result_code, path_str, message, extract)
        result_code: "CACHE_VALID" | "CACHE_STALE" | "RAW" | "ERROR"
        extract: 抽出するファイル（解決先のリポジトリルート相対パス）。解決先が
        リポジトリ内のファイルとして存在するときだけ値を持ち、それ以外は None
        （`RAW` では 2 番目と同じ値）。
    """
    mgmt_path = repo_root / mgmt_rel
    if not mgmt_path.is_file():
        return ("ERROR", mgmt_rel, "the management file does not exist", None)

    existing = mgmt_path.read_text(encoding="utf-8-sig")
    source_type = parse_frontmatter_source_type(existing)
    if source_type != "path":
        return ("ERROR", mgmt_rel, f"source.type is not path (currently: {source_type})", None)

    source_path = parse_frontmatter_source_path(existing)
    if not source_path:
        return ("ERROR", mgmt_rel, "source.path is not set", None)

    raw_path = repo_root / source_path
    # Checked before the existence test: a hand-written
    # management file can name `../../secret` or an absolute path, and
    # CACHE_STALE's "no longer exists" reason would reveal whether that file
    # exists. Outside the repository is an ERROR, not CACHE_STALE — the source
    # could never be registered in that form, so re-extracting it is not the
    # fix; the management file is.
    # One resolution serves both the containment check and the RAW target, so
    # a link swapped between two resolutions cannot hand back an unchecked path
    # (the same reason as `resolve_source_cache_path.py`'s `_target_inside`).
    target = _source_target(raw_path, repo_root)
    if target is None:
        return ("ERROR", mgmt_rel, f"source.path resolves outside the repository: {source_path}", None)

    # Existence and the hash go through `target` too, not through
    # `raw_path` again: re-opening the link would resolve it a second time, and
    # a link swapped in between would hash one file and extract another.
    target_path = repo_root / target
    extract = target.as_posix() if target_path.is_file() else None

    # Before the cache path is derived: a `.md` / `.txt` source needs no cache,
    # so a management file in an old `.wikicommit/ingest/` tree still gets its
    # answer.
    if target.suffix.lower() in RAW_TEXT_SUFFIXES and extract is not None:
        return ("RAW", extract, "read it directly; a .md / .txt source is never cached", extract)

    cache_path = extract_cache_path(mgmt_path, repo_root)
    if cache_path is None:
        return (
            "ERROR",
            mgmt_rel,
            "the management file is not under .wikicommit/source/path/, so no cache path "
            "can be derived for it (a legacy .wikicommit/ingest/ tree is never "
            "auto-migrated)",
            extract,
        )
    cache_rel = cache_path.relative_to(repo_root.resolve()).as_posix()

    if extract is None:
        return ("CACHE_STALE", cache_rel, f"the source file no longer exists: {source_path}", None)

    recorded = parse_frontmatter_hash(existing)
    if not recorded or recorded == '""':
        return ("CACHE_STALE", cache_rel, "source.hash is not set", extract)

    try:
        current = sha256_file(str(target_path))
    except OSError as exc:
        # Unreadable (permissions) or gone since the is_file() above: still a
        # CACHE_STALE line naming the file, not a traceback that drops extract=.
        return ("CACHE_STALE", cache_rel, f"the source file could not be read: {exc.strerror or exc}", extract)
    if current != recorded:
        return (
            "CACHE_STALE",
            cache_rel,
            "the source file changed since it was registered, so any cache is for an older version",
            extract,
        )

    if not cache_path.is_file():
        return ("CACHE_STALE", cache_rel, "no extraction cache has been written for this source yet", extract)

    return ("CACHE_VALID", cache_rel, current, extract)


# Read raw, never cached: the file is already the extracted text. The same set
# as `resolve_source_cache_path.py`'s `_RAW_SUFFIXES` (a test keeps the two in
# step; this script stays import-free, so they are not shared by import).
RAW_TEXT_SUFFIXES = {".md", ".txt"}


def _source_target(raw_path: Path, repo_root: Path) -> Path | None:
    """`raw_path` with symlinks followed, relative to `repo_root`; None if outside
    or unresolvable. The file whose bytes are the source."""
    try:
        resolved = raw_path.resolve()
        root = repo_root.resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return resolved.relative_to(root) if resolved.is_relative_to(root) else None


def print_path_cache_path(mgmt_rel: str, repo_root: Path) -> tuple[str, str, str]:
    """キャッシュの置き場だけを印字する（抽出後の書き込み先を知るため）。

    存在は問わない — これから書く先を尋ねる呼び出しがあるため。
    """
    mgmt_path = repo_root / mgmt_rel
    if not mgmt_path.is_file():
        return ("ERROR", mgmt_rel, "the management file does not exist")
    existing = mgmt_path.read_text(encoding="utf-8-sig")
    source_type = parse_frontmatter_source_type(existing)
    if source_type != "path":
        return ("ERROR", mgmt_rel, f"source.type is not path (currently: {source_type})")
    cache_path = extract_cache_path(mgmt_path, repo_root)
    if cache_path is None:
        return (
            "ERROR",
            mgmt_rel,
            "the management file is not under .wikicommit/source/path/, so no cache path "
            "can be derived for it (a legacy .wikicommit/ingest/ tree is never "
            "auto-migrated)",
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    return ("CACHE_PATH", cache_path.relative_to(repo_root.resolve()).as_posix(), "")


# (connect, read) seconds for every request fetch_url() makes.
# markitdown calls session.get() with no timeout, and requests' default is to
# wait forever: a server that sent its headers and then stopped, or never sent
# a status line, would hold the run until the harness killed it, with nothing
# recorded. The read timeout is per socket read, not for the whole body.
FETCH_TIMEOUT = (15, 60)


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """`exc` とその `__cause__` / `__context__` の連鎖（循環に備えて同じ例外は 2 度見ない）。"""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


def _proxy_applies(url: str) -> bool:
    """この URL へのリクエストにプロキシが効くか（環境変数と NO_PROXY から決まる）。"""
    import requests

    try:
        proxies = requests.utils.get_environ_proxies(url)
        return bool(requests.utils.select_proxy(url, proxies))
    except Exception:  # noqa: BLE001 - unknown means "cannot rule the proxy out"
        return True


def _is_connection_failure(exc: BaseException, url: str | None = None) -> bool:
    """リクエストがサーバーに届かなかったか。

    `requests.exceptions.ConnectionError` の系列を基本とし、`markitdown` が例外を
    包み直しても判定が変わらないよう `__cause__` / `__context__` を辿る。ただし
    `ConnectionError` はサーバーに届いた後の失敗も含むので、次の 3 つは除く:

    - `SSLError` — TLS ハンドシェイクまで進んだ ＝ サーバーには届いている
    - 連鎖に urllib3 の `ReadTimeoutError` がある — 読み取りのタイムアウト。
      requests は本文受信中のそれを `ReadTimeout` ではなく `ConnectionError` で送出する
    - `ProtocolError` があり `MaxRetryError` を経由しない、かつその URL にプロキシが
      効いていない — サーバーがリクエストを受けてから切った。接続段階の失敗
      （名前解決・接続拒否・接続タイムアウト・プロキシの拒否）はすべて urllib3 の
      再試行の枠（`MaxRetryError`）を通るので、ここで分かれる。プロキシが効いている
      ときは、https の CONNECT をプロキシがリセットした場合と連鎖が同じになり
      区別できないので、接続失敗（保留）側に残す — 誤っても次の実行で拾われる。
      TLS ハンドシェイクの途中でリセットされた場合も `MaxRetryError` を経由せず同じ
      連鎖になるが、リクエストはまだ送られていないので接続失敗側に残す（下記
      `_failed_during_tls_handshake()`）
    """
    import requests

    try:
        from urllib3.exceptions import MaxRetryError, ProtocolError, ReadTimeoutError
    except ImportError:  # pragma: no cover - urllib3 always ships with requests
        MaxRetryError = ProtocolError = ReadTimeoutError = ()  # type: ignore[assignment]

    chain = _exception_chain(exc)
    if not any(isinstance(e, requests.exceptions.ConnectionError) for e in chain):
        return False
    if any(isinstance(e, requests.exceptions.SSLError) for e in chain):
        return False
    if ReadTimeoutError and any(isinstance(e, ReadTimeoutError) for e in chain):
        return False
    if (
        ProtocolError
        and any(isinstance(e, ProtocolError) for e in chain)
        and not any(isinstance(e, MaxRetryError) for e in chain)
        and url is not None
        and not _proxy_applies(url)
        and not _failed_during_tls_handshake(chain)
    ):
        return False
    return True


def _failed_during_tls_handshake(chain: list[BaseException]) -> bool:
    """連鎖のどれかが TLS ハンドシェイクの最中（`ssl` の `do_handshake`）に送出されたか。

    ファイアウォールやサンドボックスが接続を受け付けてからハンドシェイク中に
    リセットすると、requests は `ConnectionError → ProtocolError → ConnectionResetError`
    を送出し、`MaxRetryError` を経由しない — サーバーがリクエストを受けてから切った
    場合と例外の型は同じである。違いは送出された場所だけで、前者ではリクエストが
    まだ送られていない。`do_handshake` は標準ライブラリ `ssl` の名前なので、
    urllib3 の内部の関数名より変わりにくい。
    """
    for e in chain:
        tb = e.__traceback__
        while tb is not None:
            if tb.tb_frame.f_code.co_name == "do_handshake":
                return True
            tb = tb.tb_next
    return False


def _session_with_timeout(requests_module, timeout):
    """Every request made through the returned session gets `timeout` unless it passes one."""

    class _TimeoutSession(requests_module.Session):
        def request(self, method, url, **kwargs):
            kwargs.setdefault("timeout", timeout)
            return super().request(method, url, **kwargs)

    return _TimeoutSession()


def fetch_url(url: str, output: str, repo_root: Path) -> tuple[str, str, str]:
    """
    URL を WikiCommit 独自 User-Agent で `markitdown` の Python API 経由でフェッチ・変換し、
    結果を output に書き込む（type: url / type: wikicommit 向け）。

    `markitdown` CLI にそのまま URL を渡すと、内部で使う requests の既定 User-Agent が
    Wikimedia 系ドメインに 403 Forbidden で拒否される。`requests.Session` に独自 UA を
    設定し `MarkItDown(requests_session=...)` へ渡すことで、`convert_uri`/`convert_response`
    が本来行う HTTP レスポンスヘッダ（Content-Type の charset・mimetype）に基づく変換方式の
    自動判定はそのまま保ったまま UA だけを差し替える（curl 等でいったんローカルファイルに
    落としてから変換する方式は、この charset ヘッダの情報が失われ文字化けを起こすため採用しない）。

    URL が取得元の差し替え表（`FETCH_SOURCE_OVERRIDES`）に当たるときは、画面の代わりに
    表が返す候補を取得し、その本文をそのまま output に書く（`_fetch_first_found()`）。

    Returns:
        (result_code, output_path_str, message)
        result_code: "FETCHED" | "NETWORK_UNAVAILABLE" | "ERROR"

    `NETWORK_UNAVAILABLE` は「接続段階で失敗した」— 名前解決・接続拒否・プロキシ拒否・
    接続タイムアウト（`requests.exceptions.ConnectionError` の系列）— ことを表し、
    ソースではなく環境の問題として `ERROR`（404・変換失敗・`ReadTimeout` 等、そのソースに
    固有の失敗）と分ける。Pass 1 は前者を `status: failed` にせず保留し、
    連続したら処理全体を止める — ガード C と同じ線引きである。
    サーバーに届いた後の失敗（読み取りのタイムアウト・リクエスト受信後の切断）は
    `ConnectionError` として送出されても `ERROR` にする（`_is_connection_failure()`）。
    すべてのリクエストに `FETCH_TIMEOUT` を与える — 無いと本文の途中で
    止まったサーバーを永久に待つ。名前解決の失敗は消えたドメイン
    （ソースの問題）でも起きるため 1 件では判断できず、それが「連続 2 件で停止」の理由である。
    """
    import requests
    from markitdown import MarkItDown

    session = _session_with_timeout(requests, FETCH_TIMEOUT)
    session.headers.update({"User-Agent": USER_AGENT})

    text = None
    candidates, _label = fetch_source_override(url)
    if candidates:
        code, text, msg = _fetch_first_found(session, candidates)
        if code != "FOUND" and code != "NOT_FOUND":
            return (code, output, msg)

    if text is None:
        md = MarkItDown(requests_session=session)
        try:
            text = md.convert_url(url).text_content
        except Exception as e:  # noqa: BLE001 - surfaced verbatim as an extraction failure
            code = "NETWORK_UNAVAILABLE" if _is_connection_failure(e, url) else "ERROR"
            return (code, output, f"{type(e).__name__}: {e}")

    out_path = Path(output)
    if not out_path.is_absolute():
        out_path = repo_root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return ("FETCHED", str(out_path), "")


def _fetch_first_found(session, candidates: list[str]) -> tuple[str, str | None, str]:
    """候補の URL を順に取得し、最初に 200 を返したものの本文を返す。

    Returns:
        ("FOUND", 本文, "") | ("NOT_FOUND", None, "") | ("ERROR" | "NETWORK_UNAVAILABLE", None, 理由)

    404 だけを「無い」として次の候補へ進む。それ以外の失敗（レート制限・5xx・
    接続の失敗）はその場で返す — 次の候補や元の URL の取得に進むと、同じソースが
    取れた経路によって別の hash を持つことになる。
    """
    for candidate in candidates:
        try:
            resp = session.get(candidate, allow_redirects=True)
        except Exception as e:  # noqa: BLE001 - classified like the markitdown fetch
            code = "NETWORK_UNAVAILABLE" if _is_connection_failure(e, candidate) else "ERROR"
            return (code, None, f"{type(e).__name__}: {e} ({candidate})")
        if resp.status_code == 404:
            continue
        if resp.status_code != 200:
            return ("ERROR", None, f"HTTP {resp.status_code} for {candidate}")
        body = resp.content
        target = _symlink_target(candidate, body)
        if target:
            # raw.githubusercontent.com serves a symlinked README as the link's target
            # path, not the file GitHub renders. Follow it once; a 404 means the body
            # was a one-line README after all, so keep it.
            try:
                linked = session.get(target, allow_redirects=True)
            except Exception as e:  # noqa: BLE001 - classified like the markitdown fetch
                code = "NETWORK_UNAVAILABLE" if _is_connection_failure(e, target) else "ERROR"
                return (code, None, f"{type(e).__name__}: {e} ({target})")
            if linked.status_code == 200:
                body = linked.content
            elif linked.status_code != 404:
                return ("ERROR", None, f"HTTP {linked.status_code} for {target}")
        # Decode as UTF-8 regardless of the Content-Type charset: raw.githubusercontent.com
        # serves text/plain, and requests' fallback for that is ISO-8859-1. `utf-8-sig`
        # drops a leading BOM, as markitdown's own decoding does.
        return ("FOUND", body.decode("utf-8-sig", errors="replace"), "")
    return ("NOT_FOUND", None, "")


_SYMLINK_TARGET_RE = re.compile(rb"\A[\w.\-/]*[./][\w.\-/]*\Z")


def _symlink_target(candidate: str, body: bytes) -> str:
    """本文が symlink の参照先パス（1 行・空白なし・255 バイト以下）に見えるなら、解決した URL を返す。"""
    if not body or len(body) > 255 or not _SYMLINK_TARGET_RE.match(body):
        return ""
    resolved = urljoin(candidate, body.decode("ascii"))
    if resolved == candidate or url_host(resolved) != url_host(candidate):
        return ""
    return resolved


# `/html/<id>` の有無を確かめる取得のタイムアウト（connect, read）秒。
ARXIV_PROBE_TIMEOUT = (10, 20)


def _arxiv_html_exists(html_url: str) -> bool:
    """`/html/<id>` が本文を返すか（200）。失敗（ネットワーク不通等）は例外として上げる。"""
    import requests

    resp = requests.get(
        html_url,
        headers={"User-Agent": USER_AGENT},
        timeout=ARXIV_PROBE_TIMEOUT,
        allow_redirects=True,
        stream=True,
    )
    try:
        # リダイレクトで `/abs/` 等へ戻された 200 を「HTML あり」と読まない。
        final_path = urlsplit(resp.url).path
        return resp.status_code == 200 and final_path.startswith("/html/")
    finally:
        resp.close()


def arxiv_candidate_url(url: str, html_exists=None) -> tuple[str, str]:
    """collect の候補に載せる URL を返す。

    arXiv の `/abs/<id>` なら本文の URL — `/html/<id>` があればそれ、無ければ
    `/pdf/<id>` — を `("FULLTEXT", <url>)` で返す。`/html/` は LaTeXML の変換が無い
    論文には無く、確かめずに出すと登録後の取得が失敗して `status: failed` になる
    ので、1 回取得して確かめる。確かめる取得自体が失敗したら、存在が確実な
    `/pdf/` に倒す。`/abs/` でなければ `("UNCHANGED", url)`。
    """
    paper_id = arxiv_abs_id(url)
    if not paper_id:
        return ("UNCHANGED", url)
    html_url, pdf_url = arxiv_fulltext_urls(paper_id)
    probe = html_exists or _arxiv_html_exists
    try:
        exists = probe(html_url)
    except Exception:  # noqa: BLE001 - any failure to confirm falls back to /pdf/
        exists = False
    return ("FULLTEXT", html_url if exists else pdf_url)


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


def _report_license_not_recorded(
    result: str, path: str, license_id: str, repo_root: Path
) -> None:
    """`--license` が指定されたのに管理ファイルを新規作成しなかったとき、捨てたことを 1 行印字する。

    既存の管理ファイルは書き換えない（人が直した値を機械が壊さない。data §4.3）。その方針は
    変えず、指定が記録されなかったことと直す場所だけを伝える — 黙っていると利用者は記録されたと
    思い込む。ERROR は結果そのものが失敗なので対象にしない。
    """
    if not license_id or result in ("CREATED", "ERROR"):
        return
    # 同じ値が既に記録されているなら、捨てたものは無い（--license 付きの再実行）。
    try:
        recorded = parse_frontmatter_license((repo_root / path).read_text(encoding="utf-8-sig"))
    except OSError:
        recorded = ""
    if recorded == license_id:
        return
    print(
        f"LICENSE_NOT_RECORDED: {path} (--license {license_id} was not recorded: this source "
        f"was already registered, and --license never rewrites an existing management file; to change it, "
        f"edit source.license in {path} directly)"
    )


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
        "--check-path-cache",
        metavar="INGEST_FILE",
        help="For a type: path source, check whether its extraction cache is still valid for the "
        "file's current version (read-only; never touches source.hash). Prints RAW with the file "
        "to read for a .md / .txt source (judged on the symlink's target), CACHE_VALID with "
        "the cache path, or CACHE_STALE with extract=<the file to extract> and the reason. "
        "Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--path-cache-path",
        metavar="INGEST_FILE",
        help="Print where a type: path source's extraction cache belongs, creating the parent "
        "directory. Does not require the cache to exist — this is asked before writing it. "
        "Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--fetch-url",
        metavar="URL",
        help="Fetch URL with markitdown using a WikiCommit User-Agent (avoids the 403s that "
        "Wikimedia domains return for markitdown's default User-Agent) and write the "
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
        "management files are never rewritten — edit them directly instead; a "
        "LICENSE_NOT_RECORDED: line says so whenever the value was not recorded.",
    )
    parser.add_argument(
        "--license-for-url",
        metavar="URL",
        help="Look up URL's host in the known-domain license table and print the result, without "
        "registering anything (read-only). Lets wikicommit-collect show the same deterministic "
        "license on a candidate that registration would record on it. Ignores the "
        "positional 'source' argument.",
    )
    parser.add_argument(
        "--fulltext-url-for",
        metavar="URL",
        help="If URL is an arXiv /abs/<id> landing page (abstract only), print the full-text "
        "URL to offer instead: FULLTEXT: https://arxiv.org/html/<id> when that exists, else "
        "https://arxiv.org/pdf/<id> (also when the check itself fails). Otherwise print "
        "UNCHANGED: <url>. Registers nothing; always exits 0. Lets wikicommit-collect offer "
        "the full text rather than the abstract. Ignores the positional 'source' argument.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root path (default: current directory)",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    # The value is free text a person typed. A line break in it would end the
    # single-quoted scalar's line and put the rest at the top level of the
    # frontmatter, where the line-based readers (`^status:` …) take it for a field.
    args.license = " ".join(args.license.split())

    # Read-only lookup: the same table registration uses, one step earlier.
    # wikicommit-collect calls this so its candidate list can show
    # the license a candidate would be registered with — and, for ShareAlike, the
    # obligation the resulting page would inherit — while the human can still
    # decline. Registration also warns, but by then the source is in.
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

    # Read-only lookup for wikicommit-collect's candidate list: offer an arXiv
    # paper by its full-text URL rather than its abstract-only /abs/ page, so the
    # registration-time partial-extraction notice need not send the person back.
    if args.fulltext_url_for:
        code, out_url = arxiv_candidate_url(args.fulltext_url_for)
        print(f"{code}: {out_url}")
        return 0

    if args.fetch_url:
        if not args.output:
            print("ERROR: --fetch-url requires --output", file=sys.stderr)
            return 1
        result, path, msg = fetch_url(args.fetch_url, args.output, repo_root)
        if result == "FETCHED":
            print(f"FETCHED: {path}")
            return 0
        if result == "NETWORK_UNAVAILABLE":
            # A distinct exit code as well as a distinct prefix, so a caller that only
            # reads the exit status cannot fold it back into ERROR.
            print(
                f"NETWORK_UNAVAILABLE: {args.fetch_url}: {msg} — the request never reached "
                "the server (name resolution, connection or proxy failed). This is usually "
                "the environment, not the source: a sandbox with network access off, a proxy, "
                "or no connection.",
                file=sys.stderr,
            )
            return 3
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

    if args.check_path_cache:
        result, path, msg, extract_file = check_path_cache(args.check_path_cache, repo_root)
        # The file to extract, symlinks followed, from the same
        # resolution check_path_cache hashed: Pass 1 routes on its
        # extension, not on the link's name.
        extract = f" extract={extract_file}" if extract_file else ""
        if result == "RAW":
            print(f"RAW: {path} ({msg})")
            return 0
        if result == "CACHE_VALID":
            print(f"CACHE_VALID: {path} ({msg})")
            return 0
        if result == "CACHE_STALE":
            print(f"CACHE_STALE: {path}{extract} ({msg})")
            return 1
        # ERROR is handled like CACHE_STALE by Pass 1, so it still names the
        # file to extract when there is one (an old `.wikicommit/ingest/` tree's
        # link to a PDF).
        print(f"ERROR: {path}{extract}: {msg}", file=sys.stderr)
        return 1

    if args.path_cache_path:
        result, path, msg = print_path_cache_path(args.path_cache_path, repo_root)
        if result == "CACHE_PATH":
            print(f"CACHE_PATH: {path}")
            return 0
        print(f"ERROR: {path}: {msg}", file=sys.stderr)
        return 1

    source = args.source
    if not source:
        print(
            "ERROR: source is required unless one of "
            "--write-hash/--check-hash/--check-path-cache/--path-cache-path/"
            "--fetch-url/--license-for-url/--fulltext-url-for is given",
            file=sys.stderr,
        )
        return 1
    counts: dict = {"created": 0, "updated": 0, "skipped": 0, "rechecked": 0, "retracted": 0}
    has_error = False

    if source.startswith("https://") or source.startswith("http://"):
        result, path, msg = process_url(source, repo_root, args.license)
        has_error = _tally(result, path, msg, counts)
        _report_license_not_recorded(result, path, args.license, repo_root)
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
            # here too, matching process_file()'s own normalization.
            rel_path = Path(abs_path).relative_to(repo_root).as_posix()
            result, path, msg = process_file(rel_path, repo_root, index, args.license)
            if _tally(result, path, msg, counts):
                has_error = True
            _report_license_not_recorded(result, path, args.license, repo_root)
    else:
        result, path, msg = process_file(source, repo_root, None, args.license)
        has_error = _tally(result, path, msg, counts)
        _report_license_not_recorded(result, path, args.license, repo_root)

    c, u, s, r = counts["created"], counts["updated"], counts["skipped"], counts["rechecked"]
    rt = counts["retracted"]
    print(f"SUMMARY: created={c}, updated={u}, skipped={s}, rechecked={r}, retracted={rt}")
    return 1 if has_error else 0


def main() -> int:
    return main_from_args()


if __name__ == "__main__":
    sys.exit(main())
