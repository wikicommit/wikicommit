#!/usr/bin/env python3
"""Detect Claude Code tool names in the distributed Skills' instructions.

The Skills were written against Claude Code's tool set — "read it with the Read tool",
"fetch it with the WebFetch tool", "run these as direct Bash-tool invocations". No other
agent has tools by those names: Codex has a shell and `apply_patch`, nothing called
`Read` or `WebFetch`. An agent that meets one either reinterprets it or skips the line,
and nothing in the output says which (Issue #1015).

Issue #1015 rewrote every such instruction by its role instead ("read the file in full",
"edit the target page", "a plain text search"), and moved the two source re-fetches in
`wikicommit-fix` / `wikicommit-review` onto `add_source.py --fetch-url` — the fetcher
`wikicommit-generate` already uses — because there the choice of tool changes what is
fetched. Subagent instructions were already written this way ("Launch a subagent"),
which is the baseline this check holds the rest to.

Scope: the same files `check_skill_tree_paths.py` walks (every `.md` under the
distributed Skills except CHANGELOG / changelog / the hand-run guides). The match spans
line breaks, since the Skills' prose is hard-wrapped and "the Bash\\ntool" is the same
instruction as "the Bash tool".

What is not matched: the bare word "Read" or "Write" (ordinary English), and the
`/wikicommit-…` invocation notation — that one is addressed where it reaches a person
(the init "Next steps" guidance and the tracking-Issue bodies say once how Codex spells
it), not in every cross-reference an agent reads.

Usage:
    python tools/check_skill_tool_names.py

Exit code: 1 if any ERROR, else 0.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check_skill_tree_paths import collect_files  # noqa: E402

TOOL_NAME_RE = re.compile(
    r"`?\b(?:Read|Write|Edit|MultiEdit|Grep|Glob|Bash|Task|NotebookEdit)\b`?(?:\s+|-)tools?\b"
    r"|\bWebFetch\b|\bWebSearch\b"
)


def main() -> int:
    errors = 0
    files = collect_files()
    for path in files:
        text = path.read_text(encoding="utf-8-sig")
        for match in TOOL_NAME_RE.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            name = " ".join(match.group(0).split())
            print(
                f"ERROR: {path}:{lineno}: Claude Code tool name {name!r} — say what to do "
                "(read the file, edit the page, search the text, run the command) rather "
                "than which tool does it, since other agents have no tool by that name "
                "(Issue #1015)"
            )
            errors += 1
    print(f"SUMMARY: checked={len(files)}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
