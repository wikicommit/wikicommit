#!/usr/bin/env python3
"""Stop `Issue #NNN` references from growing in what WikiCommit distributes.

The public repository is a snapshot push and carries no Issues, so an `Issue #527`
in a distributed file is as untraceable at its destination as a `docs/` path
(Issue #549), and in an instruction file it is paid for on every invocation.
Design history belongs in `docs/`; the distributed files keep the instruction and,
where it stops an agent from taking a plausible wrong turn, a short reason
(Issue #1054).

Two scopes, with different strengths:

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

Only the number is checked. A history sentence without a number ("previously this
was X") cannot be detected mechanically.

Usage:
    python tools/check_distributed_issue_refs.py

Exit code: 1 if any ERROR, else 0.
"""

import ast
import re
import sys
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

ISSUE_RE = re.compile(r"Issue #\d+")

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
            for match in ISSUE_RE.finditer(node.value):
                hits.append((node.lineno, match.group(0)))
    return sorted(hits)


def main() -> int:
    errors = 0

    scripts = distributed_scripts()
    for path in scripts:
        for lineno, ref in script_output_refs(path):
            print(f"ERROR: {path}:{lineno}: {ref!r} in a string the script prints "
                  f"— readers of the output cannot look it up")
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

    print(f"SUMMARY: scripts={len(scripts)}, instruction_refs={total}, errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
