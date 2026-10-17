"""Every distributed schema template's body is a reader-questions block.

docs/DesignDoc-data.md section 5.2 ("移行の状況") states that all distributed
types — the base-type templates and default.md — have moved from a body of
fixed `##` headings to a fenced `READER QUESTIONS (<Type>)` block. Nothing else
keeps that true: Pass 3 still reads the heading form (a wiki can hold older
type files), so a template that slipped back would generate pages without any
error. The one heading a template may carry after the block is a fixed section
that something reads by name across pages (section 5.2, "ブロックの後に置いた
`##` 見出しは固定の節である"); `## Key Points` on the article types is the only
one, and tests/test_schema_template_key_points.py owns which types carry it.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_SCHEMA_DIR = (
    REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "schema"
)

sys.path.insert(0, str(REPO_ROOT / ".wikicommit" / "scripts"))
from _frontmatter import parse_frontmatter_and_body_text  # noqa: E402

FIXED_SECTIONS = {"## Key Points"}
FENCE_RE = re.compile(r"^```text\nREADER QUESTIONS \((?P<name>[^)]+)\)\n.*?^```$", re.MULTILINE | re.DOTALL)


def _body_of(path: Path) -> str:
    frontmatter, error, body = parse_frontmatter_and_body_text(
        path.read_text(encoding="utf-8-sig")
    )
    assert not error, f"{path}: {error}"
    assert frontmatter, f"{path}: frontmatter block is missing or empty"
    return body


def _templates() -> list[Path]:
    templates = sorted(TEMPLATE_SCHEMA_DIR.glob("*.md"))
    # A rename or move must not turn the check below into a vacuous pass.
    assert len(templates) >= 12 and (TEMPLATE_SCHEMA_DIR / "default.md") in templates
    return templates


def test_every_template_body_opens_with_its_reader_questions_block():
    offenders = []
    for template in _templates():
        body = _body_of(template).lstrip("\n")
        match = FENCE_RE.match(body)
        if not match:
            offenders.append(f"{template.name}: body does not open with a READER QUESTIONS block")
            continue
        if match.group("name") != template.stem:
            offenders.append(
                f"{template.name}: block is labelled ({match.group('name')}), "
                f"expected ({template.stem})"
            )
        rest = body[match.end():]
        stray = [
            line for line in rest.splitlines()
            if line.startswith("#") and line.strip() not in FIXED_SECTIONS
        ]
        if stray:
            offenders.append(f"{template.name}: headings outside the block: {stray}")
    assert offenders == [], (
        "distributed schema templates must keep the reader-questions body "
        "(docs/DesignDoc-data.md section 5.2): " + "; ".join(offenders)
    )
