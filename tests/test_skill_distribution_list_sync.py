"""install.sh の配布対象 Skill リストと .claude-plugin/plugin.json の skills
配列の同期を検証する (Issue #372)。

両者は `npx skills add` 経由（plugin.json の `skills` フィールドが対象を決める。
docs/DesignDoc-skills.md §11.1「`npx skills add` 仕様確認結果」参照）と
`install.sh`（`SKILLS=(...)` 配列が対象を決める）という別々のインストール経路の、
それぞれ独立したソースオブトゥルースである。Skill の追加・削除時に片方だけ
更新して同期を忘れると、2つのインストール経路が配布する Skill 集合が
無言で食い違う。

生成スクリプト化（どちらかを正としてもう一方を自動生成する）は、
plugin.json 側に skills 以外の多数のフィールド（name・description・author 等）
があり単純な生成に向かないため見送り、代わりに
`tests/test_template_mirror_sync.py` / `tests/test_quartz_plugins_lang_segment_sync.py`
と同じ「内容一致を CI で強制する」軽量パターンを採用した。
"""

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
PATH_REF_CHECKER = REPO_ROOT / "tools" / "check_distributed_path_refs.py"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"

SKILLS_ARRAY_RE = re.compile(r'^SKILLS=\((.*)\)$', re.MULTILINE)
SKILL_PATH_PREFIX = "./.claude/skills/"


def _install_sh_skills() -> set[str]:
    text = INSTALL_SH.read_text(encoding="utf-8")
    match = SKILLS_ARRAY_RE.search(text)
    assert match, (
        f"{INSTALL_SH} に `SKILLS=(...)` 配列が見つかりません。"
        " install.sh の配列定義が変更された場合は"
        " tests/test_skill_distribution_list_sync.py の SKILLS_ARRAY_RE も更新してください。"
    )
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _plugin_json_skills() -> set[str]:
    manifest = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    skills = manifest["skills"]
    result = set()
    for entry in skills:
        assert entry.startswith(SKILL_PATH_PREFIX), (
            f"{PLUGIN_JSON}: skills エントリが想定するプレフィックス "
            f"{SKILL_PATH_PREFIX!r} で始まっていません: {entry!r}"
        )
        result.add(entry[len(SKILL_PATH_PREFIX):])
    return result


def test_install_sh_skills_array_is_non_empty():
    assert _install_sh_skills(), "install.sh の SKILLS=(...) 配列が空です"


def test_plugin_json_skills_is_non_empty():
    assert _plugin_json_skills(), f"{PLUGIN_JSON} の skills 配列が空です"


def test_install_sh_and_plugin_json_distribute_the_same_skill_set():
    install_sh_skills = _install_sh_skills()
    plugin_json_skills = _plugin_json_skills()

    assert install_sh_skills == plugin_json_skills, (
        "install.sh と .claude-plugin/plugin.json が配布する Skill 集合が"
        f" 一致していません（drift 検知。Issue #372）。"
        f" install.sh のみ: {install_sh_skills - plugin_json_skills or None}"
        f" / plugin.json のみ: {plugin_json_skills - install_sh_skills or None}"
    )


def _path_ref_checker_skills() -> set[str]:
    """The DISTRIBUTED_SKILLS list inside tools/check_distributed_path_refs.py."""
    text = PATH_REF_CHECKER.read_text(encoding="utf-8")
    match = re.search(r"DISTRIBUTED_SKILLS = \[(.*?)\]", text, re.DOTALL)
    assert match, (
        "tools/check_distributed_path_refs.py の DISTRIBUTED_SKILLS が見つかりません。"
        "リスト定義が変更された場合はこのテストの正規表現も更新してください"
    )
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def test_path_ref_checker_covers_every_distributed_skill():
    """3 つ目の配布リスト。ここから漏れた Skill は「漏れ」として報告されない —
    単に走査されないだけなので、blocking なガードが通ったまま、その Skill が持つ
    配布先から辿れないパスが検査されずに出荷される（Issue #713 の
    `wikicommit-update` が実際にこれで一度すり抜けた）。

    install.sh 側を正とする: あちらは実際にファイルをコピーする主体であり、
    このリストはそれを走査するための写しである。
    """
    assert _path_ref_checker_skills() == _install_sh_skills()
