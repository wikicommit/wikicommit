"""Open tracking Issues are fetched without a hidden 1000-item ceiling (Issue #1062).

`gh issue list --label ...` routes through GitHub's search API, which stops at
1000 results with no warning whatever `--limit` says. A distributed Skill that
lists open tracking Issues that way loses every Issue past the thousandth, and
`wikicommit-merge` then opens a duplicate for the same page on every run. The
fetch is the REST issues list with `--paginate`; this guard stops the old form
from coming back — in any distributed Skill, on any line.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
from check_skill_md_lines import instruction_files  # noqa: E402

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
FETCH_SITES = [
    ("wikicommit-merge", "labels=wikicommit-review&state=open&per_page=100"),
    ("wikicommit-merge", "labels=wikicommit-generation-failure&state=open&per_page=100"),
    ("wikicommit-review", "labels=wikicommit-review&state=open&per_page=100"),
]


def _instruction_files():
    # SKILL.md and references/ only: the CHANGELOG copy in wikicommit-init records
    # the old command on purpose, and it is history rather than an instruction.
    return [p for d in sorted(SKILLS.glob("wikicommit-*")) for p in instruction_files(d)]


def test_no_distributed_skill_lists_issues_by_label_with_gh_issue_list():
    offenders = []
    for path in _instruction_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "gh issue list" in line and "--label" in line:
                offenders.append(f"{path.relative_to(SKILLS)}:{lineno}")
    assert not offenders, (
        "`gh issue list --label` stops at 1000 results through the search API; "
        "fetch with `gh api \"repos/{owner}/{repo}/issues?labels=...\" --paginate` instead: "
        + ", ".join(offenders)
    )


@pytest.mark.parametrize("skill,query", FETCH_SITES)
def test_each_fetch_site_uses_the_paginated_rest_list(skill, query):
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    assert f'gh api "repos/{{owner}}/{{repo}}/issues?{query}"' in text
    start = text.index(query)
    assert "--paginate" in text[start:start + 200], f"{skill}: the {query} fetch lost --paginate"
    assert "select(.pull_request | not)" in text[start:start + 200], (
        f"{skill}: the REST issues list also returns PRs; the {query} fetch must drop them"
    )
