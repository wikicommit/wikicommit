#!/usr/bin/env python3
"""Fail a branch that changes the distributed payload without touching CHANGELOG.md.

`CHANGELOG.md` is the only way a user of the distribution repository learns what
changed (Issue #577), and its header states which changes get an entry
(Issue #1016). That criterion is prose: before this check, the only thing that
stopped a missing entry was someone remembering to look at `[Unreleased]` while
the PR was open — and ten changes in a row were missed that way (Issue #1029).

What counts as the payload: every file under `.claude/skills/wikicommit-*`,
except

* the CHANGELOG copies the Skill tree carries (`wikicommit-init/CHANGELOG.md`,
  `wikicommit-init/changelog/`) — they are the entry, not the change;
* rebuilt build output (`dist/`), which follows a source change already entered;
* test files of the template tree (`*.test.*`, `*.spec.*`, `test/`, `__tests__/`,
  `__mocks__/`), which change nothing a user runs or reads.

`tests/` and `docs/` at the repository root are outside the payload by
construction (the path filter above), so a change confined to them never needs
an entry or an exemption.

What counts as an entry: the branch touches the root `CHANGELOG.md` (the copy
you edit; `tests/test_changelog_sync.py` keeps the Skill-tree copy in step).

The exemption: a commit on the branch carries the trailer

    Changelog: none — <reason>

The reason is required — an empty one is an ERROR, as with the
`skill-vocabulary-exception` marker of `check_skill_user_facing_vocabulary.py`
(Issue #588): stating why the CHANGELOG criterion's "nothing a user runs or reads
behaves differently" applies is the point of the exemption. A trailer rather than
a PR-body marker so that the same check runs locally (the fallback when Actions
minutes run out) and needs nothing but `git`. The record does not have to survive
the squash merge — the check judges the branch, before it lands.

The range is `merge-base(<base>, HEAD)..HEAD` — committed changes only;
uncommitted edits are not looked at. `<base>` defaults to `origin/main`; CI on a
pull_request event passes the PR's base explicitly.

Usage:
    python tools/check_changelog_entry.py [--base <rev>]

Exit code: 1 if the payload changed with neither an entry nor a valid
exemption, or if an exemption has no reason; 0 otherwise.
"""

import argparse
import re
import subprocess
import sys

PAYLOAD_PREFIX = ".claude/skills/wikicommit-"
CHANGELOG = "CHANGELOG.md"
CHANGELOG_COPIES = (
    ".claude/skills/wikicommit-init/CHANGELOG.md",
    ".claude/skills/wikicommit-init/changelog/",
)
EXCLUDED_SEGMENTS = {"dist", "test", "__tests__", "__mocks__"}
TEST_FILE_RE = re.compile(r"\.(test|spec)\.[^/]+$")
TRAILER_KEY = "Changelog"
# `none`, then a dash (em dash, en dash or hyphen) or a colon, then the reason.
EXEMPTION_RE = re.compile(r"^none\s*(?:[—–:-]\s*(.*))?$", re.IGNORECASE)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def is_payload(path: str) -> bool:
    if not path.startswith(PAYLOAD_PREFIX):
        return False
    if any(path == c or (c.endswith("/") and path.startswith(c)) for c in CHANGELOG_COPIES):
        return False
    if EXCLUDED_SEGMENTS.intersection(path.split("/")[:-1]):
        return False
    return not TEST_FILE_RE.search(path)


def parse_exemptions(trailer_values: list[str]) -> tuple[list[str], list[str]]:
    """Split `Changelog:` trailer values into (reasons, malformed values)."""
    reasons, bad = [], []
    for value in trailer_values:
        m = EXEMPTION_RE.match(value.strip())
        reason = (m.group(1) or "").strip() if m else ""
        if reason:
            reasons.append(reason)
        else:
            bad.append(value.strip())
    return reasons, bad


def judge(changed: list[str], trailer_values: list[str]) -> tuple[int, list[str]]:
    """Return (exit code, output lines) for a branch's changed paths and trailers."""
    payload = [p for p in changed if is_payload(p)]
    reasons, bad = parse_exemptions(trailer_values)
    lines = [
        f"ERROR: `{TRAILER_KEY}: {v}` has no reason — write `{TRAILER_KEY}: none — <why no user "
        "notices this change>`"
        for v in bad
    ]
    if not payload:
        lines.append("OK: no distributed payload changed on this branch")
    elif CHANGELOG in changed:
        lines.append(f"OK: {len(payload)} payload file(s) changed and {CHANGELOG} was touched")
    elif reasons:
        lines.append(
            f"OK: {len(payload)} payload file(s) changed; exempted by trailer "
            f"({'; '.join(reasons)})"
        )
    else:
        shown = ", ".join(payload[:5]) + (f" (+{len(payload) - 5} more)" if len(payload) > 5 else "")
        lines.append(
            f"ERROR: the distributed payload changed ({shown}) but {CHANGELOG} was not touched. "
            f"Add a line under [Unreleased] (see \"Which changes get an entry\" at the top of "
            f"{CHANGELOG}), or, if nothing a user runs or reads behaves differently, add the "
            f"commit trailer `{TRAILER_KEY}: none — <reason>`"
        )
    failed = any(line.startswith("ERROR:") for line in lines)
    return (1 if failed else 0), lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="origin/main", help="branch the PR targets")
    args = parser.parse_args()

    try:
        merge_base = git("merge-base", args.base, "HEAD").strip()
    except subprocess.CalledProcessError as e:
        print(f"ERROR: cannot find the merge base of {args.base} and HEAD: {e.stderr.strip()}")
        return 1
    # --no-renames: a payload file moved out of the payload must still show its old path.
    # -z: raw paths (the default output C-quotes non-ASCII names, defeating the prefix test).
    diff = git("diff", "--name-only", "--no-renames", "-z", f"{merge_base}..HEAD")
    changed = [p for p in diff.split("\0") if p]
    trailers = git(
        "log", f"--format=%(trailers:key={TRAILER_KEY},valueonly,unfold)", f"{merge_base}..HEAD"
    )
    code, lines = judge(changed, [t for t in trailers.splitlines() if t.strip()])
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
