"""Guards that `config.yml` does not regrow a `review:` block (Issue #669).

`review.auto_merge` and `review.chain_of_thought` shipped in the template from
Phase 1 on with no consumer anywhere — neither `.claude/skills/*/SKILL.md` nor
`.wikicommit/scripts/*.py` ever read either one. The cost was not the unread
value; it was that the value read as a control that existed. A design
conversation began from "set `auto_merge: false` on `Person` and merging stops",
which could not work: there is no global gate to narrow, let alone a per-type
one.

Two assertions, because the failure has two shapes. The first is the block
coming back; the second is a consumer never arriving for a key that did. The
repo's own rule (Issue #553 / #564) is that a key ships with its consumer, and
a test is the only thing that states it about `config.yml` itself.
"""

import re
from pathlib import Path

import pytest
import yaml

from _publication import skip_unless_development_repository

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "config.yml"
OWN_CONFIG = REPO_ROOT / ".wikicommit" / "config.yml"

DEAD_KEYS = ("auto_merge", "chain_of_thought")


@pytest.mark.parametrize("path", [TEMPLATE, OWN_CONFIG], ids=["template", "own"])
def test_config_has_no_review_block(path):
    if path == OWN_CONFIG:
        # This repository dogfoods WikiCommit, so it has a config of its own — but
        # that config is its wiki data, not a distributed artifact, and is
        # permanently excluded from the published snapshot (Issue #788). The
        # template half of this parametrisation is the one that guards the
        # shipped default, and it runs everywhere.
        skip_unless_development_repository("this repository's own .wikicommit/config.yml")
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "review" not in parsed, (
        f"{path} grew a `review:` block again. Both of its former keys had no "
        "consumer; if one is being reintroduced, land it together with the code "
        "that reads it (Issue #553 / #669)."
    )


@pytest.mark.parametrize("key", DEAD_KEYS)
def test_removed_keys_are_not_reintroduced_without_a_consumer(key):
    """A key may come back — but only alongside something that reads it.

    Scanned: everywhere a wiki repository's own `config.yml` could be read from
    — the distributed Skills, the shared scripts (reached through the
    `templates/scripts/` originals that `.wikicommit/scripts/` symlinks to), and
    the workflow templates `init.py` also ships, which is where an `auto_merge`
    consumer would most naturally live. A bare mention in prose does not count
    as a consumer, so the search is for the key appearing somewhere other than a
    config file.

    Matching is on a word boundary rather than a substring, because a substring
    scan for `auto_merge` hits `allow_auto_merge` in `wikicommit-merge/SKILL.md`
    — the GitHub repository setting that merely shares a name (Issue #456), and
    the very confusion Issue #669 is about. Left as a substring test, this
    assertion would report a consumer that does not exist and pass for exactly
    the key it most needs to guard.
    """
    # OWN_CONFIG is absent from the published snapshot (see above); dropping it
    # there narrows what is scanned but cannot make this assertion pass wrongly —
    # a key declared only in the template is still caught by the template half.
    configs = [path for path in (TEMPLATE, OWN_CONFIG) if path.is_file()]
    declared_in = [
        path for path in configs
        if re.search(rf"^\s*{re.escape(key)}\s*:", path.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    if not declared_in:
        return  # Still removed, which is this Issue's outcome.

    skills = REPO_ROOT / ".claude" / "skills"
    searched = list(skills.rglob("SKILL.md"))
    searched += list(skills.rglob("scripts/*.py"))
    searched += list(skills.rglob("templates/workflows/*.yml"))
    mention = re.compile(rf"(?<![\w-]){re.escape(key)}(?![\w-])")
    consumers = [p for p in searched if mention.search(p.read_text(encoding="utf-8"))]
    assert consumers, (
        f"`{key}` is declared in {[str(p) for p in declared_in]} but nothing in "
        "the Skills, their scripts, or the workflow templates reads it. That is "
        "the state Issue #669 removed: a field that reads as a control and "
        "controls nothing."
    )
