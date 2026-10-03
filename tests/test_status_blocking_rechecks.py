"""`/wikicommit-status` が merge の blocking な 3 本を全ページに走らせていることを固定する（Issue #976）。

`validate_frontmatter.py` / `check_wikilinks.py` / `check_raw_html.py` は
`wikicommit-merge` が変更ファイルにしか走らせない。一度書かれたページには
status 以外の誰も走らせないため、ここから外れると「書かれた後に壊れたページ」を
報告する主体が無くなる — しかも外れても何も落ちない。

`check_wikilinks.py` は `--skip-type-mismatch` 付きで呼ぶ。Type セグメントの
取り違えは `check_wanted_pages.py` の `TYPE_MISMATCH:` が既に報告しており、
フラグが無いと同じ所見が 2 回出る。重複の除去を SKILL.md の散文（メッセージ
文言での除外）に委ねないため、フラグの有無をここで固定する。
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
STATUS_SKILL = REPO_ROOT / ".claude" / "skills" / "wikicommit-status" / "SKILL.md"


def _commands() -> list[str]:
    text = STATUS_SKILL.read_text(encoding="utf-8")
    return re.findall(r"^python \.wikicommit/scripts/(\S+\.py.*)$", text, flags=re.MULTILINE)


def test_status_runs_the_three_blocking_checks_unscoped():
    commands = _commands()
    for script in ("validate_frontmatter.py", "check_raw_html.py"):
        assert script in commands, f"{script} must be run with no arguments (every page)"


def test_status_calls_check_wikilinks_with_skip_type_mismatch():
    commands = [c for c in _commands() if c.startswith("check_wikilinks.py")]
    assert commands == ["check_wikilinks.py --skip-type-mismatch"]
