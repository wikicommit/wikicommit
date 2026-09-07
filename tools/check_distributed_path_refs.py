#!/usr/bin/env python3
"""Detect development-repository paths referenced from distributed artifacts.

`install.sh` ships `.claude/skills/wikicommit-*/` to a user's wiki repository,
and `wikicommit-init` expands `.claude/skills/wikicommit-init/scripts/templates/`
into that repository's own `.wikicommit/` tree. Neither destination contains
this repository's `docs/`, `Issues/`, or `dev/` directories, so a citation
pointing at one of them is untraceable wherever it actually lands. In a SKILL.md
it is also paid for on every invocation, since the whole file is loaded into the
agent's context (Issue #549).

Design-rationale tracking runs `docs/` -> distributed artifact, not the other
way around: `docs/DesignDoc-*.md` referencing a SKILL.md stays inside the
development repository and is out of scope here.

`templates/quartz-plugins/` used to be reported as DEFERRED rather than failed,
because its `dist/` is committed and editing `src/` without a per-package npm
rebuild would desync the two. Those references are gone and the plugins have
been rebuilt (Issue #644), so every distributed file is now held to the same
rule and the DEFERRED label no longer exists. Clearing a reference there means
rebuilding the package, not only editing the source: the committed build
outputs carry the comment too. `.js.map` is scanned for exactly that reason —
its `sourcesContent` embeds each `src/` file verbatim, and it is usually the
*only* shipped copy, since the bundler drops most comments from `dist/*.js`
(before Issue #644 removed them, the ten references lived in the maps of all
three plugins but in the `dist/*.js` of just one). Scanning only `dist/*.js`
would therefore let a missing rebuild pass silently.

Usage:
    python tools/check_distributed_path_refs.py

Exit code: 1 if any ERROR, else 0.
"""

import os
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")

# Kept in sync with install.sh's SKILLS array — enforced by
# tests/test_skill_distribution_list_sync.py, because a Skill missing from here is not
# reported as an omission: it is simply never walked, so this blocking guard passes while
# the new Skill's undistributed paths ship unchecked. That is how wikicommit-update
# (Issue #713) first slipped through.
DISTRIBUTED_SKILLS = [
    "wikicommit-init", "wikicommit-generate", "wikicommit-merge", "wikicommit-review",
    "wikicommit-remove", "wikicommit-fix", "wikicommit-status", "wikicommit-collect",
    "wikicommit-search", "wikicommit-ask", "wikicommit-quiz", "wikicommit-synthesize",
    "wikicommit-serve", "wikicommit-translate", "wikicommit-schema-propose",
    "wikicommit-update",
]

# Directories that only exist in this development repository. `docs/` is
# narrowed to its actual contents (DesignDoc-*.md only) so that an illustrative
# path in a Skill's own example output — `docs/notes/meeting-0512.md` in
# wikicommit-collect's candidate list — is not mistaken for a real citation.
# The `docs/` prefix is optional: a bare `DesignDoc-data.md §4.2` names the same
# undistributed file and is just as unresolvable at the destination, so matching
# only the prefixed form would leave a trivial way to re-introduce one.
# The lookbehind excludes `.` as well as word characters, `/` and `-` so that a
# `.dev` top-level domain in a URL (`https://vite.dev/config/`) is not read as a
# reference to this repository's `dev/` directory; a genuine reference is never
# immediately preceded by `.` (a relative `./dev/` or `../dev/` ends in `/`).
DEV_ONLY_PATH_RE = re.compile(
    r"(?<![\w./-])(?:(?:docs/)?DesignDoc-[\w.-]*[\w]|(?:Issues|dev)/[\w./-]*[\w/])"
)

SKIP_DIRS = {"node_modules", "__pycache__", ".git"}
TEXT_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".js", ".map", ".yml", ".yaml",
                 ".json", ".sh", ".toml"}


def collect_files() -> list[Path]:
    roots = [SKILLS_DIR / name for name in DISTRIBUTED_SKILLS]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        # Prune skipped directories during the walk rather than filtering
        # afterwards: quartz-plugins/*/node_modules/ alone holds enough entries
        # to make a full rglob() traversal take minutes.
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                path = Path(dirpath) / name
                if path.suffix in TEXT_SUFFIXES:
                    files.append(path)
    return sorted(set(files))


def main() -> int:
    error_count = 0
    checked_count = 0

    for path in collect_files():
        checked_count += 1
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in DEV_ONLY_PATH_RE.finditer(line):
                print(f"ERROR: {path}:{lineno}: development-repository path "
                      f"{match.group(0)!r} is not resolvable where this file is distributed")
                error_count += 1

    print(f"SUMMARY: checked={checked_count}, errors={error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
