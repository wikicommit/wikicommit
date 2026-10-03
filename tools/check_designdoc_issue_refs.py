#!/usr/bin/env python3
"""Keep the history out of the DesignDocs that have been split (Issue #1138).

`docs/DesignDoc-*.md` is split one file at a time into the current specification
(the DesignDoc) and its history (`docs/history/<same name>.md`). Once a file is
split, a new Issue that appends its reasoning to the body puts it back the way it
was. This guard counts `Issue #NNN` in each split DesignDoc and fails when the
count grows past its cap. The cap may only be lowered.

Only files listed in CAPS are checked; the rest have not been split yet. Add a
file to CAPS in the same change that splits it, at the count it has after the
split. Only the number is checked — a history sentence without a number
("previously this was X") cannot be detected mechanically; CONTRIBUTING.md states
the rule and PR review enforces the rest.

Usage:
    python tools/check_designdoc_issue_refs.py

Exit code: 1 if any ERROR, else 0.
"""

import re
import sys
from pathlib import Path

ISSUE_RE = re.compile(r"Issue #\d+")

# Per-file ceiling on `Issue #NNN` in a split DesignDoc. May only be lowered.
CAPS = {
    "docs/DesignDoc-pipeline.md": 3,
    "docs/DesignDoc-data.md": 0,
    "docs/DesignDoc-skills.md": 0,
    "docs/DesignDoc-publish.md": 0,
    "docs/DesignDoc-ScriptSpec.md": 0,
}


def count(path: Path) -> int:
    return len(ISSUE_RE.findall(path.read_text(encoding="utf-8-sig")))


def main() -> int:
    errors = 0
    for rel, cap in CAPS.items():
        path = Path(rel)
        history = Path("docs/history") / path.name
        if not path.exists():
            print(f"ERROR: {rel} is listed in CAPS but does not exist")
            errors += 1
            continue
        if not history.exists():
            print(f"ERROR: {rel} is listed in CAPS but {history} does not exist")
            errors += 1
        n = count(path)
        if n > cap:
            print(f"ERROR: {rel}: {n} `Issue #` reference(s), cap is {cap} "
                  f"— write the current spec here and the history in {history}")
            errors += 1
        elif n < cap:
            print(f"NOTE: {rel}: {n} reference(s), below the cap of {cap}; lower CAPS[{rel!r}] to {n}")
    print(f"SUMMARY: split_docs={len(CAPS)}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
