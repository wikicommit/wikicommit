"""`wikicommit-review` / `wikicommit-fix` read a source's text, not a summary (Issue #1047).

Both Skills used to re-read a URL source with the agent's web-fetch tool, which in
Claude Code returns a model-written summary — so a review checked the page against a
summary while its record claimed the page's recorded hash. The route is now the
extraction cache first (`resolve_source_cache_path.py`), then `add_source.py
--fetch-url` into `.wikicommit/.cache/refetch/`. The route lives only in prose, so
these tests hold it in place.
"""

from pathlib import Path

import pytest

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
TEXTS = {
    name: (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
    for name in ("wikicommit-review", "wikicommit-fix")
}


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_cache_is_asked_before_any_fetch(name):
    text = TEXTS[name]
    cache = text.index("../wikicommit-ask/scripts/resolve_source_cache_path.py")
    fetch = text.index("../wikicommit-generate/scripts/add_source.py --fetch-url")
    assert cache < fetch, f"{name} fetches before asking for the extraction cache"


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_fetch_lands_outside_the_extraction_cache(name):
    text = TEXTS[name]
    assert ".wikicommit/.cache/refetch/" in text
    commands = [line for line in text.splitlines() if "add_source.py" in line and "python" in line]
    assert commands and not any("--write-hash" in line for line in commands), (
        f"{name} would move source.hash, which only wikicommit-generate may do"
    )


@pytest.mark.parametrize("name", sorted(TEXTS))
def test_network_unavailable_is_reported_as_the_environment(name):
    assert "NETWORK_UNAVAILABLE:" in TEXTS[name]
    assert "the environment" in TEXTS[name]


def test_review_records_a_version_mismatch_in_the_note_not_as_a_finding():
    text = TEXTS["wikicommit-review"]
    assert "whose hash differs from the one this page records" in text
    assert "Do not raise it as a finding" in text
    assert "version-mismatch lines from Step 4 item 1" in text
