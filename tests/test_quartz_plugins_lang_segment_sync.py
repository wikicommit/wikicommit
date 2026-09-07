"""quartz-plugins 3 種の LANG_SEGMENT_RE 定義の同期を検証する (Issue #228)。

`wikicommit-breadcrumbs` / `wikicommit-language-switcher` / `wikicommit-explorer`
は独立した npm パッケージで、3者間で共有するワークスペース・パッケージは存在しない
（`.wikicommit/entity/<lang>/` の `<lang>` セグメントを判定する
`const LANG_SEGMENT_RE = /^[a-z]{2}$/` がそれぞれの src/ に個別にハードコードされている）。

真にランタイムで共有する仕組み（monorepo ワークスペース・公開 npm パッケージ経由の
import 等）は、tsup の各パッケージ独立ビルド・rootDir を跨ぐ tsconfig の制約・
Quartz のローカルプラグイン解決の挙動が未検証であることを踏まえると、この 1 行の
正規表現定数を共有するためだけに導入するには釣り合わないビルドインフラ変更になる
（p3-043 の tsup.config.ts 共有化検討がまさに同種の重量級検討として Phase 3 の間
未着手のまま残っている）。

そのため、3 プラグイン側は意図的に定義を複製したまま維持し、代わりに
`tests/test_template_mirror_sync.py` と同じ「内容一致を CI で強制する」パターンを
採用した。3 ファイルいずれかで `LANG_SEGMENT_RE` の正規表現リテラルだけが変更され、
他の 2 つが古いロジックのまま取り残される drift を検知する。
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PLUGINS_DIR = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "quartz-plugins"
)

# (プラグインディレクトリ名, LANG_SEGMENT_RE を定義するソースファイル) の一覧。
# Issue #228 の対象ファイル。
LANG_SEGMENT_SOURCES = [
    (
        "wikicommit-breadcrumbs",
        PLUGINS_DIR / "wikicommit-breadcrumbs" / "src" / "components" / "WikiCommitBreadcrumbs.tsx",
    ),
    (
        "wikicommit-language-switcher",
        PLUGINS_DIR
        / "wikicommit-language-switcher"
        / "src"
        / "components"
        / "WikiCommitLanguageSwitcher.tsx",
    ),
    (
        "wikicommit-explorer",
        PLUGINS_DIR / "wikicommit-explorer" / "src" / "util" / "foldLang.ts",
    ),
]

LANG_SEGMENT_RE_DEFINITION = re.compile(r"^const LANG_SEGMENT_RE = (/.+/)$", re.MULTILINE)


def _extract_lang_segment_regex(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = LANG_SEGMENT_RE_DEFINITION.search(text)
    assert match, (
        f"{path} に `const LANG_SEGMENT_RE = /.../` の定義が見つかりません。"
        " Issue #228 のファイルが移動/リネームされた場合は"
        " tests/test_quartz_plugins_lang_segment_sync.py の LANG_SEGMENT_SOURCES も更新してください。"
    )
    return match.group(1)


def test_lang_segment_sources_exist():
    for plugin_name, path in LANG_SEGMENT_SOURCES:
        assert path.is_file(), f"{plugin_name}: ソースファイルが見つかりません: {path}"


def test_lang_segment_regex_is_identical_across_plugins():
    patterns = {plugin_name: _extract_lang_segment_regex(path) for plugin_name, path in LANG_SEGMENT_SOURCES}

    distinct_patterns = set(patterns.values())
    assert len(distinct_patterns) == 1, (
        "LANG_SEGMENT_RE の正規表現が3プラグイン間で一致していません"
        f"（drift 検知。Issue #228）: {patterns}"
    )
