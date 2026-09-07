"""Guards the commit-trailer convention against a hardcoded model ID (#559).

`Generated-By` exists to track precisely which model produced a commit, so a
literal model ID baked into a SKILL.md's commit command defeats its only
purpose — and contradicts the `generated_by` frontmatter written by the very
same commit, since that one *is* self-reported at run time. The trailers were
literals (`claude-sonnet-4-6`) until Issue #559 turned them into placeholders;
this test keeps them that way, because the failure is silent: a wrong trailer
looks exactly like a right one until someone compares it against the pages in
the same commit.
"""

import re
from pathlib import Path

import pytest

from _publication import is_development_repository

REPO_ROOT = Path(__file__).parent.parent

# The three trailers that name a model. `Reviewed-by`/`Signed-off-by` name a
# human and are out of scope (see docs/DesignDoc-pipeline.md §6.7).
TRAILER_RE = re.compile(
    r"^\s*(Co-Authored-By|Generated-By|Reviewed-By-AI):\s*(.+?)\s*$",
    re.IGNORECASE,
)

# A model ID written out rather than left as a `<...>` placeholder. Matches the
# vendor-prefixed form these trailers use (`claude-sonnet-4-6`,
# `claude-opus-5[1m]`, ...) plus the human-readable display name.
HARDCODED_RE = re.compile(r"claude[-\s][a-z0-9]", re.IGNORECASE)


# The prose statements of the convention. Unlike the SKILL.md glob (whose
# membership legitimately changes as skills come and go), these are named
# explicitly, so a missing one means the convention moved — not that it stopped
# applying. Assert rather than skip: silently dropping a renamed file would let
# a hardcoded model ID come back with this guard still green.
CONVENTION_DOCS = (
    Path("CLAUDE.md"),
    Path("CONTRIBUTING.md"),
    Path("docs/DesignDoc-pipeline.md"),
)


def _files_under_convention() -> list[Path]:
    """Every file that either states the trailer convention or applies it."""
    files = sorted((REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"))
    convention_docs = [REPO_ROOT / rel for rel in CONVENTION_DOCS]
    if not is_development_repository():
        # Parametrizing over a file that is not in this checkout would fail on
        # read_text() rather than skip, so filter here as well as in the
        # existence check below.
        convention_docs = [path for path in convention_docs if path.exists()]
    return files + convention_docs


def test_convention_documents_still_exist():
    if not is_development_repository():
        pytest.skip("published snapshot: convention docs are intentionally absent")
    missing = [str(rel) for rel in CONVENTION_DOCS if not (REPO_ROOT / rel).exists()]
    assert not missing, (
        "these files state the commit-trailer convention and must stay under this "
        "guard; if one was renamed or split, update CONVENTION_DOCS to follow it "
        f"(Issue #559): {missing}"
    )


@pytest.mark.parametrize("path", _files_under_convention(), ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_model_trailers_are_placeholders_not_literals(path):
    offenders = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        m = TRAILER_RE.match(line)
        if not m:
            continue
        # Strip every `<...>` span: that covers both the placeholders this
        # convention requires and the fixed `<noreply@anthropic.com>` literal,
        # leaving only text an author wrote out directly.
        value = re.sub(r"<[^>]*>", "", m.group(2))
        if HARDCODED_RE.search(value):
            offenders.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")

    assert not offenders, (
        "commit trailers must use the `<Claude display name>` / `<current model ID>` "
        "placeholders, never a hardcoded model (Issue #559):\n" + "\n".join(offenders)
    )
