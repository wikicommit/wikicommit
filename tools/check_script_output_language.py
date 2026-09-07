#!/usr/bin/env python3
"""Detect Japanese text in the console output of distributed Python scripts.

`install.sh` ships `.claude/skills/wikicommit-*/scripts/` to a user's wiki
repository, and `wikicommit-init` expands
`.claude/skills/wikicommit-init/scripts/templates/scripts/` into that
repository's own `.wikicommit/scripts/`. What those scripts print reaches two
readers: the operator running `/wikicommit-status` or the `/wikicommit-merge`
quality gate, and the agent that reads the same output to decide what to do
next. Neither is the wiki's audience, so the output is fixed English rather
than localized (Issue #770) — the same call Issue #405 made for the headings of
source management files.

The reason is not only that this repository is English-first (README in
English, `README_ja.md` in Japanese). Diagnostics are the canonical case of
machine-readable output that internationalization practice leaves untranslated:
error strings get pasted verbatim into search engines and issue trackers, and
translating them stops two people who hit the same problem from landing on the
same string. `ERROR:` / `WANTED:` / `TYPE_MISMATCH:` are exactly that kind of
structured diagnostic.

Comments and docstrings are deliberately out of scope: their reader is the
developer, which matches `docs/` being written in Japanese. This mirrors the
line Issue #583 drew when it unified the "ingest" vocabulary — only one layer
moves.

`ast` is used rather than `grep` precisely so that comments and docstrings are
not swept in. f-string constant parts count, because they are literal output
just as much as a plain string is; interpolated values do not, because their
content is only known at run time.

Known limitation: a message that is *returned* rather than printed is invisible
here. `.wikicommit/scripts/_frontmatter.py` is the shape to watch — it hands its
error text back to its callers, which then print it, and its only `print()` call
interpolates that text as a variable, so nothing it produces is reachable from
here. (Its own strings were translated with the rest of Issue #770; the point is
that a future regression there would not be caught.) Scripts written that way
have to be checked by hand.

Usage:
    python tools/check_script_output_language.py

Exit code: 1 if any ERROR, else 0.
"""

import ast
import os
import re
import sys
from pathlib import Path

SKILLS_DIR = Path(".claude/skills")

SKIP_DIRS = {"node_modules", "__pycache__", ".git"}

# Hiragana, katakana, CJK punctuation, CJK ideographs (including extension A)
# and fullwidth forms. Latin punctuation that reads as "Japanese style" (the em
# dash used across this repository's prose, for instance) is intentionally not
# matched — it is language-neutral.
CJK_RE = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿＀-￯]")


def collect_files() -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(SKILLS_DIR):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if Path(dirpath).name != "scripts":
            continue
        for name in filenames:
            if name.endswith(".py"):
                files.append(Path(dirpath) / name)
    return sorted(set(files))


def literal_parts(node: ast.AST):
    """Yield every string literal that ends up verbatim in the printed text."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                yield value.value
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # "a" + "b" and, more usefully, an implicit-concatenation chain that a
        # formatter has split with `+`.
        yield from literal_parts(node.left)
        yield from literal_parts(node.right)


def main() -> int:
    error_count = 0
    checked_count = 0

    for path in collect_files():
        checked_count += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError) as err:
            print(f"ERROR: {path}: could not be parsed: {err}")
            error_count += 1
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "print"):
                continue
            for arg in node.args:
                for text in literal_parts(arg):
                    match = CJK_RE.search(text)
                    if match is None:
                        continue
                    print(f"ERROR: {path}:{node.lineno}: print() output contains "
                          f"Japanese text ({match.group(0)!r}); distributed script "
                          f"output is fixed English")
                    error_count += 1
                    break

    print(f"SUMMARY: checked={checked_count}, errors={error_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
