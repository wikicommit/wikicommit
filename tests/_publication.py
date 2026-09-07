"""Whether this checkout is the development repository or the published snapshot.

`wikicommit/wikicommit` is built by copying a whitelist of paths out of this
repository (`dev/scripts/snapshot_push.sh`), so it is a strict subset: `dev/`,
`Issues/`, `CLAUDE.md`, `CONTRIBUTING.md`, `CHANGELOG_ja.md`, `.gitignore` and
`.wikicommit/config.yml` are not in it. A test that reads one of those has
nothing to check there, and skipping is correct behaviour rather than a hole.

**The missing file cannot itself be the signal**, though — that is exactly what
a rename looks like, and catching renames is usually the whole point of the
guard. So the discriminator is the repository kind, and each guard then asserts
that its own inputs are present when it runs in the development repository.

`Issues/` is the discriminator: it is on the permanent-exclusion list (never
published at any phase), it is a directory rather than a file so a rename of any
single document cannot be mistaken for it, and nothing in the development
repository works without it.

Shared rather than copied because the same three-sentence rationale was already
being restated per file, and because the count of guards that need it keeps
growing — 3 failures (2026-08-31) → 4 (09-01) → 14 (09-07) → 16, with the
increase driven not by new tests but by the publication boundary moving under
tests that look unrelated to it (Issue #660 / #788). One place to state the rule
is also one place to find every guard that depends on it.

When you add a test that reads a `REPO_ROOT` path outside the published set,
use this helper **and** record the file in `dev/publication-scope.md` §5 — that
section is the list of ways the public subset can break quietly.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent


def is_development_repository() -> bool:
    """True in this repository, False in the published snapshot."""
    return (REPO_ROOT / "Issues").is_dir()


def skip_unless_development_repository(what: str) -> None:
    """Skip the calling test when running against the published snapshot.

    `what` names the input that is intentionally absent there, so the skip
    reason says which file is missing and why that is expected.
    """
    if not is_development_repository():
        pytest.skip(f"published snapshot: {what} is intentionally not published")
