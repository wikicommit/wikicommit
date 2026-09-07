"""Guards the "no H1 in a wiki page body" convention (Issue #546).

Every distributed schema template's body is copied verbatim as the shape of a
generated wiki page, so "no template body uses an H1" *is* the convention —
there was no other statement of it anywhere until Issue #546 wrote it down in
docs/DesignDoc-data.md §4.1. `/wikicommit-synthesize` was the one Skill that
builds a body without going through a template, and its Step 5 told the agent
to open the document with the topic as a heading; that produced the single
page under .wikicommit/entity/ whose body carried an H1
(dev/pilot-ai-driven-dev-wiki-round5.md).

The page title belongs to the `title` frontmatter field, which Quartz renders
as the page heading, so a body H1 duplicates it on the published page.
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

# ATX H1 only: "# x". Setext ("x\n===") is checked separately below.
ATX_H1_RE = re.compile(r"^# \S", re.MULTILINE)
SETEXT_H1_RE = re.compile(r"^(?!\s*$).+\n=+\s*$", re.MULTILINE)


def _body_of(path: Path) -> str:
    """Return the Markdown body, dropping the leading YAML frontmatter block.

    Delegates to the shared production parser rather than splitting here: four
    tests in this directory read the same template set, and each carrying its
    own split is how `.wikicommit/scripts/_frontmatter.py` came to exist in the
    first place (Issue #704 — its module docstring lists the real bugs the
    divergent copies produced). The body variant is text-based, so the file is
    read with utf-8-sig to match that module's own `parse_frontmatter()`:
    otherwise a BOM-prefixed template looks like one with no frontmatter, and
    the whole file — frontmatter included — comes back as the body.
    """
    frontmatter, error, body = parse_frontmatter_and_body_text(
        path.read_text(encoding="utf-8-sig")
    )
    assert not error, f"{path}: {error}"
    assert frontmatter, f"{path}: frontmatter block is missing or empty"
    return body


def schema_templates() -> list[Path]:
    return sorted(TEMPLATE_SCHEMA_DIR.rglob("*.md"))


def test_schema_template_dir_is_populated():
    """A rename or move must not turn the two checks below into vacuous passes."""
    templates = schema_templates()
    assert len(templates) >= 12, f"expected the full base-type set, found {len(templates)}"
    assert (TEMPLATE_SCHEMA_DIR / "default.md") in templates


def test_no_schema_template_body_uses_an_h1():
    offenders = []
    for template in schema_templates():
        body = _body_of(template)
        if ATX_H1_RE.search(body) or SETEXT_H1_RE.search(body):
            offenders.append(str(template.relative_to(REPO_ROOT)))
    assert offenders == [], (
        "schema template bodies must start at `##` or a paragraph — the page title "
        f"lives in the `title` frontmatter field (Issue #546). Offenders: {offenders}"
    )


def test_synthesize_skill_does_not_ask_for_a_top_heading():
    """The Step 5 wording that caused Issue #546, kept out by name.

    Dropping the instruction alone would leave the convention implicit in the
    templates, so Step 5 states the prohibition instead; this asserts the
    original positive phrasing has not come back.
    """
    skill_md = (
        REPO_ROOT / ".claude" / "skills" / "wikicommit-synthesize" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "as a heading at the top of the document" not in skill_md
    assert "Do not open the body with an H1" in skill_md
