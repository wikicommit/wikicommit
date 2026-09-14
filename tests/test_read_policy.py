"""Tests for .wikicommit/scripts/read_policy.py (Issue #844).

The point of the script is that "is this body still the shipped example" stops
being a judgment call, so these tests are mostly about the ways a body can state
nothing — and about the one direction the old arrangement failed in, where the
example's own suggestions (all of which argue for excluding something) could be
applied as if the wiki had chosen them.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parent.parent
    / ".claude"
    / "skills"
    / "wikicommit-init"
    / "scripts"
    / "templates"
    / "scripts"
    / "read_policy.py"
)
TEMPLATES = SCRIPT.parent.parent


def run(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True
    )


def write(tmp_path: Path, body: str, frontmatter: str = "wikicommit:\n  exclude_domains: []\n") -> Path:
    path = tmp_path / "policy.md"
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")
    return path


def test_a_written_policy_is_returned(tmp_path):
    result = run(write(tmp_path, "\nPrefer primary sources.\nNo personal blogs.\n"))
    assert result.returncode == 0
    assert result.stdout.startswith("POLICY:")
    assert "Prefer primary sources." in result.stdout
    assert "No personal blogs." in result.stdout


def test_the_frontmatter_is_never_part_of_the_prose(tmp_path):
    result = run(write(tmp_path, "\nPrefer primary sources.\n"))
    assert "exclude_domains" not in result.stdout


def test_an_empty_body_states_nothing(tmp_path):
    result = run(write(tmp_path, ""))
    assert result.stdout.startswith("NONE:")
    assert "the body is empty" in result.stdout


def test_a_missing_file_states_nothing(tmp_path):
    result = run(tmp_path / "absent.md")
    assert result.returncode == 0
    assert result.stdout.startswith("NONE:")
    assert "is not present" in result.stdout


def test_the_shipped_example_states_nothing(tmp_path):
    """The marked block is named as such, so the reader knows nobody has touched it."""
    result = run(write(tmp_path, "\n<!-- wikicommit:example\nPrefer primary sources.\n-->\n"))
    assert result.stdout.startswith("NONE:")
    assert "still the worked example" in result.stdout


def test_an_empty_frontmatter_block_is_still_stripped(tmp_path):
    """A `---`/`---` block with no keys left in it is frontmatter, not policy.

    The regex this used to use (`\\A---\\n.*?\\n---`) cannot match a block with zero
    content lines, so the delimiters stayed in the body: a file whose body was only
    the shipped example came back as POLICY with `---` as its prose. _frontmatter.py
    documents that exact pitfall, which is why the split is delegated to it.
    """
    result = run(write(tmp_path, "\n<!-- wikicommit:example\nPrefer primary sources.\n-->\n", frontmatter=""))
    assert result.returncode == 0
    assert result.stdout.startswith("NONE:")
    assert "---" not in result.stdout

    result = run(write(tmp_path, "\nTake in city open data.\n", frontmatter=""))
    assert result.stdout.startswith("POLICY:")
    assert result.stdout.splitlines()[1] == "Take in city open data."


def test_a_file_in_another_encoding_is_reported_not_raised(tmp_path):
    """The contract is one line and exit 0 however the read failed.

    UnicodeDecodeError is a ValueError, so catching only OSError let a policy file
    saved in a legacy encoding traceback out of a script every caller expects to
    print exactly one POLICY:/NONE: line.
    """
    path = tmp_path / "policy.md"
    path.write_bytes("---\nwikicommit: {}\n---\n\n一次資料を優先する。\n".encode("shift_jis"))
    result = run(path)
    assert result.returncode == 0
    assert result.stdout.startswith("NONE:")
    assert "could not be read" in result.stdout


def test_an_example_edited_in_place_is_not_called_untouched(tmp_path):
    """Writing inside the marked comment leaves the same bytes as never touching it.

    The marker cannot tell those apart, so the reason must not assert the one it
    cannot verify — it has to say that a policy inside a comment is not read.
    """
    result = run(write(tmp_path, "\n<!-- wikicommit:example\nOnly take in city open data.\n-->\n"))
    assert result.stdout.startswith("NONE:")
    assert "inside that comment" in result.stdout
    assert "Only take in city open data" not in result.stdout


def test_a_body_commented_out_without_the_marker_states_nothing(tmp_path):
    """A repository initialized before the marker existed needs no migration.

    Its body is one unmarked HTML comment, and an HTML comment is never policy.
    The reason is worded differently on purpose: the likeliest way to get here is
    editing the example in place without deleting the `<!--`, which is worth
    saying rather than reporting as an untouched file.
    """
    result = run(write(tmp_path, "\n<!--\nDo not take in personal blogs.\n-->\n"))
    assert result.stdout.startswith("NONE:")
    assert "inside an HTML comment" in result.stdout
    assert "Do not take in personal blogs" not in result.stdout


def test_a_comment_next_to_a_real_policy_is_dropped_but_the_policy_is_not(tmp_path):
    result = run(write(tmp_path, "\n<!-- a note to self -->\n\nPrefer primary sources.\n"))
    assert result.stdout.startswith("POLICY:")
    assert "Prefer primary sources." in result.stdout
    assert "a note to self" not in result.stdout


def test_the_shipped_example_survives_alongside_a_written_policy(tmp_path):
    """Deleting the example is advice, not a requirement — the policy still wins."""
    result = run(
        write(tmp_path, "\n<!-- wikicommit:example\nDo not take in personal blogs.\n-->\n\nTake in city open data.\n")
    )
    assert result.stdout.startswith("POLICY:")
    assert "Take in city open data." in result.stdout
    assert "personal blogs" not in result.stdout


def test_both_shipped_templates_state_no_policy(tmp_path):
    """The templates as distributed must read as "no policy", or every fresh wiki
    silently adopts the example's exclusions."""
    for name in ("source-policy.md", "entity-policy.md"):
        result = run(TEMPLATES / name)
        assert result.stdout.startswith("NONE:"), name
        assert "still the worked example" in result.stdout, name


def test_both_shipped_templates_carry_the_marker():
    for name in ("source-policy.md", "entity-policy.md"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "<!-- wikicommit:example" in text, name
