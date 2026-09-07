"""wikicommit-init が配布する templates/ とのミラー同期を検証する (#73)。

drift 再発防止（[[wikicommit-init-template-drift]]）: `.wikicommit/schema/`・
`.wikicommit/scripts/` はこのリポジトリ自身のドッグフーディング用の足場であり、
配布物・テスト対象コードはいずれも `.claude/skills/wikicommit-init/scripts/templates/`
配下が唯一の実体である（`tests/test_check_*.py` 等は全て templates 側を直接
import/実行している）。かつては root 側を編集のたびに手動でテンプレートへコピー
する運用だったため、コピー漏れが Issue #71/72/73/74 → #523/#536 → #216 と繰り返し
発生していた。この対応（Issues/ 草案 `p3-216-schema-mirror-drift-issue523.md`。
GitHub Issue 未登録）で `.wikicommit/schema`・`.wikicommit/scripts` を
templates 配下への symlink に置き換え、手動コピーという drift の発生源自体を
構造的になくした（symlink なので中身は常に templates と同一になり、乖離が
そもそも起こり得ない）。以降このテストは byte 単位の内容比較ではなく、
symlink が正しいターゲットを指しているかのみを検証する。

quartz-plugins/ は元々 root にも canonical コピーを置いていたが、Issue #81 で
private リポジトリでの自己公開をやめるにあたり root から削除した。以降
templates/quartz-plugins/ が唯一のコピーとなり drift が起こり得ないため、
このミラー検証の対象からは外している。

`.markdownlint.json`（Issue #90）は上記ディレクトリ単位ペアとは事情が異なるため
別建てのテストにしている。ルート直下は本リポジトリ自身の docs/・README.md
（設計ドキュメント・ディレクトリツリーや疑似コードを多用）向けの調整であり、
Issue #89 で `MD040: false` と `MD024.siblings_only: true` を追加した。配布
テンプレート側は利用者の `.wikicommit/entity/**/*.md`（LLM が生成する Wiki ページ）
向けで、対象ルールは docs/DesignDoc-CISpec.md「`.markdownlint.json` 設定方針」の
MD041・MD013・MD033 の 3 件のみと定義されている。したがって両者が完全一致する
必然性はなく（docs/DesignDoc-TestSpec.md L4 参照）、byte 単位の一致は検証しない。
代わりに、両ファイルに共通するキーの値が矛盾していないこと（テンプレート側の
キーはすべてルート側にも存在し、同じ値であること）だけを検証し、ルート側だけの
追加ルール（MD040・MD024）による意図的な乖離は許容する。
"""

import json
import os
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
QUARTZ_CONFIG_TEMPLATE = TEMPLATES_DIR / "quartz.config.yaml"

# (symlink パス, templates からの相対ターゲット) のペア一覧。
SYMLINK_PAIRS = [
    pytest.param(REPO_ROOT / ".wikicommit" / "schema", "../.claude/skills/wikicommit-init/scripts/templates/schema", id="schema"),
    pytest.param(REPO_ROOT / ".wikicommit" / "scripts", "../.claude/skills/wikicommit-init/scripts/templates/scripts", id="scripts"),
]


@pytest.mark.parametrize("link_path,expected_target", SYMLINK_PAIRS)
def test_dogfood_dir_is_symlink_to_template(link_path: Path, expected_target: str):
    assert link_path.is_symlink(), (
        f"{link_path} は templates/ への symlink である必要があります（drift を構造的に防ぐため）"
    )
    assert os.readlink(link_path) == expected_target, (
        f"{link_path} の symlink ターゲットが想定と異なります: {os.readlink(link_path)!r} != {expected_target!r}"
    )
    assert link_path.resolve().is_dir(), f"{link_path} の symlink ターゲットが解決できません"


def test_quartz_config_template_wires_wikicommit_plugins():
    config = QUARTZ_CONFIG_TEMPLATE.read_text(encoding="utf-8")
    assert "source: ../quartz-plugins/wikicommit-jsonld" in config
    assert "source: ../quartz-plugins/wikicommit-banner" in config


@pytest.mark.parametrize("page_type", ["folder", "tag"])
def test_quartz_config_excludes_banner_from_generated_listing_pages(page_type: str):
    """#648 — Quartz 生成のフォルダ・タグページからバナーを外す。

    この2種には対応する .md の実体が無く、書き出し側で review_status: reviewed を
    スタンプする余地が無い（Issue #580 が3種のナビゲーションページに適用した手段が
    使えない）。WikiCommitBanner の review_status フォールバックが pending である以上、
    抑止はレイアウト設定側でしか行えない。
    """
    config = yaml.safe_load(QUARTZ_CONFIG_TEMPLATE.read_text(encoding="utf-8"))
    exclude = config["layout"]["byPageType"][page_type]["exclude"]
    assert "wikicommit-banner" in exclude, (
        f"byPageType.{page_type}.exclude に wikicommit-banner がありません"
        "（機械生成の目次に未レビューバナー・報告リンクが表示されます）"
    )


MARKDOWNLINT_CANONICAL = REPO_ROOT / ".markdownlint.json"
MARKDOWNLINT_TEMPLATE = TEMPLATES_DIR / ".markdownlint.json"


def test_markdownlint_template_rules_do_not_contradict_canonical():
    """テンプレート側のルールがルート側と矛盾しないことを検証する (#90)。

    完全一致ではなく、テンプレート側に定義されたキーが必ずルート側にも存在し、
    かつ同じ値であることのみを検証する。ルート側だけの追加ルール
    （MD040・MD024。Issue #89）はここではチェック対象にせず、意図的な乖離として許容する。
    """
    canonical_rules = json.loads(MARKDOWNLINT_CANONICAL.read_text(encoding="utf-8"))
    template_rules = json.loads(MARKDOWNLINT_TEMPLATE.read_text(encoding="utf-8"))

    for rule, value in template_rules.items():
        assert rule in canonical_rules, f"ルートに存在しないルールがテンプレートにあります: {rule}"
        assert canonical_rules[rule] == value, f"ルールの値が一致しません: {rule}"
