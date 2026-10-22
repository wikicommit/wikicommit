#!/usr/bin/env python3
"""Stop `Issue #NNN` references from growing in what WikiCommit distributes.

The public repository is a snapshot push and carries no Issues, so an `Issue #527`
in a distributed file is as untraceable at its destination as a `docs/` path
(Issue #549), and in an instruction file it is paid for on every invocation.
Design history belongs in `docs/`; the distributed files keep the instruction and,
where it stops an agent from taking a plausible wrong turn, a short reason
(Issue #1054).

Three scopes, with different strengths:

* **Script output** (blocking at zero). String literals in the distributed
  scripts that reach stdout / stderr or `--help` — everything except comments and
  docstrings, including the attribute docstrings `_root_outputs.py` uses. These are
  already at zero, so any new one is a regression.
* **Instruction files** (a ratchet). `SKILL.md` and `references/*.md` of each
  distributed Skill (the set `check_skill_md_lines.instruction_files()` defines),
  plus `templates/review-rules.md` and `templates/schema-authoring.md`, which the
  agent reads as instructions. Removing the references is a migration Skill by
  Skill, so the count is capped per Skill at its current value: it may only go
  down. Lower the cap in `CAPS` in the same change that removes references; when
  every cap is zero the table collapses to "none allowed".
* **Script comments and docstrings** (blocking at zero). The same distributed
  scripts, but only what the first scope skips: `#` comments and docstrings. They
  are read by whoever opens the script — in the user's repository too — and the
  history they would carry belongs in `docs/history/DesignDoc-ScriptSpec.md`
  under the script's heading (Issue #1329). Every distributed script is at zero,
  so any reference is an error, reported with its line.

In the two script scopes a reference is `Issue #NNN`, `Issue-#NNN` or a bare
`#NNN` (two or more digits); in instruction files it is `Issue #NNN` only.
Only the number is checked. A history sentence without a number ("previously this
was X") cannot be detected mechanically.

Usage:
    python tools/check_distributed_issue_refs.py

Exit code: 1 if any ERROR, else 0.
"""

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_distributed_path_refs import DISTRIBUTED_SKILLS  # noqa: E402
from check_skill_md_lines import instruction_files  # noqa: E402

SKILLS_DIR = Path(".claude/skills")
TEMPLATES_DIR = SKILLS_DIR / "wikicommit-init/scripts/templates"
TEMPLATE_INSTRUCTIONS = [
    TEMPLATES_DIR / "review-rules.md",
    TEMPLATES_DIR / "schema-authoring.md",
]

# Instruction files (Markdown) are counted on the `Issue #NNN` form only: a bare
# `#NNN` there collides with headings and anchors.
ISSUE_RE = re.compile(r"Issue #\d+")
# Scripts: `Issue #NNN`, `Issue-#NNN`, and a bare `#NNN` of two or more digits.
# The bare form excludes a `#` preceded by a word character, `&`, `#` or `/`
# (`&#123;`, `##12`, URL fragments) and one followed by a word character (hex
# colours such as `#123abc`), and a single digit (`#1` as an ordinal). Comments
# and docstrings are hard-wrapped, so "Issue" can end one line and "#NNN" start
# the next; `\s+` covers that. ASCII-only, so a CJK character next to the number
# (`参照#374で`) does not hide it the way a Unicode `\w` would.
SCRIPT_ISSUE_RE = re.compile(r"Issue(?:\s+|-)#\d+|(?<![\w&#/])#\d{2,}(?!\w)", re.ASCII)

# Per-Skill ceiling on `Issue #NNN` in instruction files. May only be lowered.
CAPS = {
    "wikicommit-init": 0,
    "wikicommit-generate": 0,
    "wikicommit-merge": 0,
    "wikicommit-review": 0,
    "wikicommit-remove": 0,
    "wikicommit-fix": 0,
    "wikicommit-status": 0,
    "wikicommit-collect": 0,
    "wikicommit-search": 0,
    "wikicommit-ask": 0,
    "wikicommit-quiz": 0,
    "wikicommit-synthesize": 0,
    "wikicommit-serve": 0,
    "wikicommit-translate": 0,
    "wikicommit-schema-propose": 0,
    "wikicommit-update": 0,
    "wikicommit-reconcile": 0,
    "wikicommit-relate": 0,
    "wikicommit-organize": 0,
}


def count(path: Path) -> int:
    return len(ISSUE_RE.findall(path.read_text(encoding="utf-8-sig")))


def distributed_scripts() -> list[Path]:
    scripts = [p for name in DISTRIBUTED_SKILLS for p in (SKILLS_DIR / name / "scripts").glob("*.py")]
    scripts += (TEMPLATES_DIR / "scripts").glob("*.py")
    return sorted(set(scripts))


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Module/class/function docstrings and attribute docstrings (a bare string
    right after an assignment) — read by developers, never printed."""
    found: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = body[0] if body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
        for prev, stmt in zip(body, body[1:]):
            if (isinstance(prev, (ast.Assign, ast.AnnAssign)) and isinstance(stmt, ast.Expr)
                    and isinstance(stmt.value, ast.Constant)):
                found.add(id(stmt.value))
    return found


def script_output_refs(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    docs = _docstring_nodes(tree)
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docs):
            for match in SCRIPT_ISSUE_RE.finditer(node.value):
                hits.append((node.lineno, " ".join(match.group(0).split())))
    return sorted(hits)


def script_comment_refs(path: Path) -> list[tuple[int, str]]:
    """Issue references in the comments and docstrings of a script — what
    `script_output_refs()` deliberately skips."""
    text = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(text, filename=str(path))
    docs = _docstring_nodes(tree)
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) in docs:
            hits += [(node.lineno + node.value.count("\n", 0, m.start()), " ".join(m.group(0).split()))
                     for m in SCRIPT_ISSUE_RE.finditer(node.value)]
    # Consecutive comment lines are joined (without their `#`) so a reference
    # wrapped across two of them is still one reference.
    runs: list[list[tuple[int, str]]] = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.COMMENT:
            continue
        entry = (tok.start[0], tok.string.lstrip("#").strip())
        if runs and runs[-1][-1][0] == entry[0] - 1:
            runs[-1].append(entry)
        else:
            runs.append([entry])
    for run in runs:
        starts, joined = [], ""
        for lineno, body in run:
            starts.append((len(joined), lineno))
            joined += body + " "
        for m in SCRIPT_ISSUE_RE.finditer(joined):
            lineno = max(line for offset, line in starts if offset <= m.start())
            hits.append((lineno, " ".join(m.group(0).split())))
    return sorted(hits)


def main() -> int:
    errors = 0

    scripts = distributed_scripts()
    for path in scripts:
        for lineno, ref in script_output_refs(path):
            print(f"ERROR: {path}:{lineno}: {ref!r} in a string the script prints "
                  f"— readers of the output cannot look it up")
            errors += 1

    script_total = 0
    for path in scripts:
        for lineno, ref in script_comment_refs(path):
            print(f"ERROR: {path}:{lineno}: {ref!r} in a comment or docstring "
                  f"— keep the history in docs/history/DesignDoc-ScriptSpec.md")
            script_total += 1
            errors += 1

    missing = sorted(set(DISTRIBUTED_SKILLS) - set(CAPS))
    for name in missing:
        print(f"ERROR: {name} has no entry in CAPS; add it (at its current count, or 0)")
        errors += 1

    total = 0
    for name in DISTRIBUTED_SKILLS:
        root = SKILLS_DIR / name
        if not root.exists():
            continue
        files = instruction_files(root)
        if name == "wikicommit-init":
            files += [p for p in TEMPLATE_INSTRUCTIONS if p.exists()]
        n = sum(count(p) for p in files)
        total += n
        cap = CAPS.get(name)
        if cap is None:
            continue
        if n > cap:
            print(f"ERROR: {name}: {n} `Issue #` reference(s) in instruction files, cap is {cap} "
                  f"— keep the history in docs/ and the instruction here")
            errors += 1
        elif n < cap:
            print(f"NOTE: {name}: {n} reference(s), below the cap of {cap}; lower CAPS[{name!r}] to {n}")

    print(f"SUMMARY: scripts={len(scripts)}, instruction_refs={total}, "
          f"script_comment_refs={script_total}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
