"""Skill-to-Skill dependencies: what the files say, what SKILL.md declares, what §11.3 lists.

A Skill depends on another when a file in its directory reads or runs a file in the
other's — an instruction naming `../wikicommit-<name>/…`, or a Skill-side script walking
to a sibling (`here.parent.parent / "wikicommit-init" / …`). Nothing declared these
before Issue #1210; finding them meant grepping for `../`, and the hand-drawn figure in
docs/DesignDoc-skills.md §11.5 had already drifted from them.

Three things must agree, and this file holds them together:

1. the references actually present in each distributed Skill's files,
2. `metadata.requires` in each SKILL.md's frontmatter (space-separated Skill names),
3. the table under "#### Skill 間の依存" in docs/DesignDoc-skills.md §11.3.

It also holds that the dependencies have no cycle: a cycle means no order of partial
installs leaves both Skills working.

What is scanned (Issue #1218): every file git tracks under a Skill directory that reads
as text — binaries alone are skipped, so a reference added in a `.sh`, `.json` or `.txt`
is not silently missed. Untracked files (the thousands under init's template
`node_modules/`) are not distributed and do not count. In any text file,
`../wikicommit-<name>/` counts. In a script (`SCRIPT_SUFFIXES`), `wikicommit-<name>` that
starts a string literal or follows a `/` glued to a path segment, and ends at a quote or a
`/`, counts too, however the path around it is built — `/ "wikicommit-init"`,
`.joinpath("wikicommit-init")`, `Path("..", "wikicommit-ask")`, `"../" + "wikicommit-ask"`,
`f"{root}/wikicommit-ask/x"`, `"$root/wikicommit-ask/x"`, `"../../wikicommit-ask"`.
A script that needs a Skill's name for something other than a path (a label, a message)
trips this and must spell it so it does not start the literal; erring that way fails
loudly instead of dropping a dependency.

Not counted: CHANGELOG.md and changelog/ (records, not instructions), and init's
`scripts/templates/` (the payload copied into `.wikicommit/`, which runs from there and
never from beside its siblings). Relations through `.wikicommit/` — shared scripts,
`review-rules.md` — are not Skill-to-Skill dependencies either: the wiki holds them.
"""

import functools
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / ".claude" / "skills"
DESIGNDOC = REPO / "docs" / "DesignDoc-skills.md"

sys.path.insert(0, str(REPO / "tools"))
from check_distributed_path_refs import DISTRIBUTED_SKILLS  # noqa: E402

INSTRUCTION_REF = re.compile(r"\.\./(wikicommit-[a-z-]+)/")
SCRIPT_REF = re.compile(r"""(?:["']|(?<=[^\s"'])/)(wikicommit-[a-z-]+)(?=["'/])""")
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts"}


def _counted(skill_dir: Path, path: Path) -> bool:
    parts = path.relative_to(skill_dir).parts
    if "__pycache__" in parts or "node_modules" in parts:
        return False
    if path.name == "CHANGELOG.md" or "changelog" in parts:
        return False
    return parts[:2] != ("scripts", "templates")


def tracked_files(skill_dir: Path) -> list[Path]:
    """Files git tracks under `skill_dir` — what is distributed, whatever else the tree holds.

    A tree with no git metadata (the public subset, staged from `git archive` of HEAD by
    dev/scripts/check_publication_subset.sh) holds only tracked files, so every file on
    disk is the same set there.
    """
    if not (REPO / ".git").exists():
        return sorted(p for p in skill_dir.rglob("*") if p.is_file())
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", str(skill_dir)],
        cwd=REPO, capture_output=True, check=True,
    ).stdout.decode("utf-8")
    return sorted(REPO / name for name in out.split("\0") if name)


def _text(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\0" in data:
        return None
    # References are ASCII, so a text file in another encoding is still scanned, not skipped.
    return data.decode("utf-8-sig", errors="replace")


def scan_references(skill_dir: Path, files: list[Path]) -> dict[str, set[str]]:
    """{other Skill: {file that references it}} over `files` inside `skill_dir`."""
    found: dict[str, set[str]] = {}
    for path in files:
        if not path.is_file() or not _counted(skill_dir, path):
            continue
        text = _text(path)
        if text is None:
            continue
        patterns = [INSTRUCTION_REF]
        if path.suffix in SCRIPT_SUFFIXES:
            patterns.append(SCRIPT_REF)
        for pattern in patterns:
            for match in pattern.finditer(text):
                other = match.group(1)
                if other != skill_dir.name:
                    found.setdefault(other, set()).add(str(path.relative_to(skill_dir.parent)))
    return found


def actual_references(skill: str) -> dict[str, set[str]]:
    """{other Skill: {file that references it}} for one distributed Skill directory."""
    skill_dir = SKILLS / skill
    return scan_references(skill_dir, tracked_files(skill_dir))


def declared_requires(skill: str) -> set[str]:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8-sig")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{skill}/SKILL.md has no frontmatter"
    front = yaml.safe_load(match.group(1)) or {}
    metadata = front.get("metadata") or {}
    value = metadata.get("requires", "")
    assert isinstance(value, str), (
        f"{skill}: metadata.requires must be one space-separated string (agentskills.io "
        f"metadata maps strings to strings), got {value!r}"
    )
    return set(value.split())


HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]|$)")
# A backtick fence's info string cannot contain a backtick (CommonMark), so a line that
# opens with inline code such as ```x``` is not a fence.
FENCE = re.compile(r"^\s*(`{3,}(?!.*`)|~{3,})")


def markdown_section(text: str, heading: str) -> str:
    """The lines from the `heading` line up to the next heading of the same or a higher level.

    Lines inside fenced code blocks (``` or ~~~) are never headings, so a `# comment` in a
    bash example does not cut the section short (Issue #1234). The heading line must match
    `heading` exactly (trailing whitespace aside).
    """
    lines = text.splitlines(keepends=True)
    fence: str | None = None
    start: int | None = None
    level = 0
    for i, line in enumerate(lines):
        bare = line.rstrip()
        if fence is None:
            opening = FENCE.match(bare)
            if opening:
                fence = opening.group(1)
                continue
        else:
            # Closes only on a run of the same character, at least as long, and nothing else.
            run = bare.strip()
            if len(run) >= len(fence) and run == fence[0] * len(run):
                fence = None
            continue
        match = HEADING.match(bare)
        if not match:
            continue
        if start is None:
            if bare.strip() == heading:
                start, level = i, len(match.group(1))
        elif len(match.group(1)) <= level:
            return "".join(lines[start:i])
    if start is None:
        raise ValueError(f"heading not found outside code blocks: {heading!r}")
    return "".join(lines[start:])


def table_pairs() -> set[tuple[str, str]]:
    section = markdown_section(DESIGNDOC.read_text(encoding="utf-8"), "#### Skill 間の依存")
    row = re.compile(r"^\| `(wikicommit-[a-z-]+)` \| `(wikicommit-[a-z-]+)` \|", re.MULTILINE)
    return {(m.group(1), m.group(2)) for m in row.finditer(section)}


ACTUAL = {skill: actual_references(skill) for skill in DISTRIBUTED_SKILLS}


def test_the_scan_sees_a_dependency_known_to_exist():
    """Guards the scanner itself: an empty result would make every test below pass."""
    assert "wikicommit-generate" in ACTUAL["wikicommit-collect"]
    assert "wikicommit-init" in ACTUAL["wikicommit-update"]
    # A script walking to a sibling counts too, not only instruction text.
    assert any(f.endswith(".py") for f in ACTUAL["wikicommit-merge"].get("wikicommit-init", ()))


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("scripts/a.py", 'p = here.parent.parent / "wikicommit-ask" / "x"\n'),
        ("scripts/a.py", 'p = here.parent.parent.joinpath("wikicommit-ask", "x")\n'),
        ("scripts/a.py", 'p = Path("..", "wikicommit-ask")\n'),
        ("scripts/a.py", 'p = "../" + "wikicommit-ask" + "/x"\n'),
        ("scripts/a.py", "p = os.path.join(here, '../wikicommit-ask/x')\n"),
        ("scripts/a.py", 'p = f"{root}/wikicommit-ask/x"\n'),
        ("scripts/a.py", 'p = "{}/wikicommit-ask".format(root)\n'),
        ("scripts/a.py", 'p = here / "../../wikicommit-ask"\n'),
        ("scripts/run.sh", 'root="$here/.."; cat $root/wikicommit-ask/x\n'),
        ("scripts/run.sh", 'python "$here/../wikicommit-ask/scripts/x.py"\n'),
        ("scripts/run.sh", 'cd "$here/.." && ls "wikicommit-ask/x"\n'),
        ("data.json", '{"path": "../wikicommit-ask/x.md"}\n'),
        ("notes.txt", "see ../wikicommit-ask/SKILL.md\n"),
        ("references/x.md", "Read `../wikicommit-ask/SKILL.md`.\n"),
        ("agents/x.yaml", "ref: ../wikicommit-ask/SKILL.md\n"),
    ],
)
def test_the_scan_catches_each_way_of_writing_a_reference(tmp_path, name, content):
    """Adding any of these to a Skill must surface as a dependency, so the tests below fail."""
    skill_dir = tmp_path / "wikicommit-demo"
    path = skill_dir / name
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    assert scan_references(skill_dir, [path]) == {"wikicommit-ask": {f"wikicommit-demo/{name}"}}


def test_the_scan_reads_a_text_file_that_is_not_utf8(tmp_path):
    skill_dir = tmp_path / "wikicommit-demo"
    path = skill_dir / "notes.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes("café: see ../wikicommit-ask/SKILL.md\n".encode("cp1252"))
    assert scan_references(skill_dir, [path]) == {"wikicommit-ask": {"wikicommit-demo/notes.txt"}}


def test_the_scan_skips_binaries_self_references_and_excluded_paths(tmp_path):
    skill_dir = tmp_path / "wikicommit-demo"
    files = {
        "img.png": b"\x89PNG\0../wikicommit-ask/",
        "scripts/a.py": b'p = here / "wikicommit-demo" / "x"\n',
        "scripts/templates/b.py": b'p = here / "wikicommit-ask"\n',
        "node_modules/c.js": b'require("../wikicommit-ask/x")\n',
        "CHANGELOG.md": b"../wikicommit-ask/\n",
        "SKILL.md": b"Run /wikicommit-ask first.\n",
        "scripts/m.py": b'print("Next, run /wikicommit-ask")\n',
    }
    paths = []
    for name, data in files.items():
        path = skill_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        paths.append(path)
    assert scan_references(skill_dir, paths) == {}


def test_the_scan_reads_only_tracked_files():
    """Untracked trees (init's template node_modules/) must not change the result."""
    files = tracked_files(SKILLS / "wikicommit-init")
    assert files and all(SKILLS / "wikicommit-init" in f.parents for f in files)
    assert not any("node_modules" in f.parts for f in files)


@pytest.mark.parametrize("skill", DISTRIBUTED_SKILLS)
def test_metadata_requires_matches_the_references(skill):
    actual = set(ACTUAL[skill])
    declared = declared_requires(skill)
    undeclared = {other: sorted(ACTUAL[skill][other]) for other in actual - declared}
    assert not undeclared, (
        f"{skill} references Skills its SKILL.md does not declare in metadata.requires: "
        f"{undeclared}. Declare them, or move what is shared into .wikicommit/scripts/ "
        "(docs/DesignDoc-skills.md §11.5)."
    )
    assert not declared - actual, (
        f"{skill} declares {sorted(declared - actual)} in metadata.requires but no file "
        "references them; drop the stale declaration."
    )


def test_every_required_skill_is_distributed():
    for skill in DISTRIBUTED_SKILLS:
        for other in declared_requires(skill):
            assert other in DISTRIBUTED_SKILLS, f"{skill} requires {other}, which is not distributed"


def test_the_designdoc_table_matches_the_references():
    actual = {(skill, other) for skill in DISTRIBUTED_SKILLS for other in ACTUAL[skill]}
    table = table_pairs()
    assert table, "no rows read from §11.3「Skill 間の依存」"
    assert actual - table == set(), (
        f"missing from docs/DesignDoc-skills.md §11.3「Skill 間の依存」: {sorted(actual - table)}"
    )
    assert table - actual == set(), (
        f"listed in §11.3「Skill 間の依存」 but not referenced: {sorted(table - actual)}"
    )


def test_the_dependencies_have_no_cycle():
    graph = {skill: declared_requires(skill) for skill in DISTRIBUTED_SKILLS}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node):] + [node]
            pytest.fail("Skill dependency cycle: " + " -> ".join(cycle))
        if node in done:
            return
        for other in sorted(graph.get(node, ())):
            visit(other, path + [node])
        done.add(node)

    for skill in DISTRIBUTED_SKILLS:
        visit(skill, [])


def test_init_depends_on_nothing():
    """init creates `.wikicommit/`; every other Skill may lean on it, not the reverse."""
    assert ACTUAL["wikicommit-init"] == {}
    assert declared_requires("wikicommit-init") == set()


# README (Issue #1217): the partial-install examples and the "Also install" table must
# follow metadata.requires, or a reader who installs only what the README names gets a
# Skill whose fallback or version check silently does nothing.

READMES = [REPO / "README.md", REPO / "README_ja.md"]
README_HEADINGS = {"README.md": "### Installing only some Skills", "README_ja.md": "### 一部の Skill だけを入れる場合"}
INSTALL_LINE = re.compile(r"^\s*npx skills add wikicommit/wikicommit(?=\s|$)(.*)$", re.MULTILINE)
SKILL_FLAG = re.compile(r"(?:--skill|-s)(?:\s+|=)['\"]?(wikicommit-[a-z-]+)")


@functools.cache
def required_closure(skill: str) -> frozenset[str]:
    """Every Skill `skill` needs, following metadata.requires through."""
    seen: set[str] = set()
    stack = [skill]
    while stack:
        for other in declared_requires(stack.pop()):
            if other not in seen:
                seen.add(other)
                stack.append(other)
    return frozenset(seen)


def readme_table(readme: Path) -> dict[str, set[str]]:
    text = readme.read_text(encoding="utf-8")
    return table_rows(markdown_section(text, README_HEADINGS[readme.name]), readme.name)


def table_rows(section: str, name: str) -> dict[str, set[str]]:
    """{Skill: {Skills it also needs}} from the two-column table rows in `section`."""
    rows: dict[str, set[str]] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 and re.fullmatch(r"`wikicommit-[a-z-]+`", cells[0]):
            skill = cells[0].strip("`")
            assert skill not in rows, f"{name}: `{skill}` has more than one row"
            rows[skill] = set(re.findall(r"`(wikicommit-[a-z-]+)`", cells[1]))
    return rows


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_readme_table_matches_metadata_requires(readme):
    expected = {s: set(c) for s in DISTRIBUTED_SKILLS if (c := required_closure(s))}
    table = readme_table(readme)
    assert table, f"no rows read from {readme.name} '{README_HEADINGS[readme.name]}'"
    assert table == expected, (
        f"{readme.name} '{README_HEADINGS[readme.name]}' disagrees with metadata.requires "
        f"(followed through). Expected {expected}, got {table}"
    )


@pytest.mark.parametrize("readme", READMES, ids=lambda p: p.name)
def test_readme_partial_install_examples_include_dependencies(readme):
    lines = INSTALL_LINE.findall(readme.read_text(encoding="utf-8"))
    named = [set(SKILL_FLAG.findall(args)) for args in lines]
    named = [skills for skills in named if skills]
    assert named, f"no `npx skills add ... --skill wikicommit-*` example found in {readme.name}"
    for skills in named:
        missing = set().union(*(required_closure(s) for s in skills)) - skills
        assert not missing, (
            f"{readme.name}: the example installing {sorted(skills)} leaves out "
            f"{sorted(missing)}, which metadata.requires says they need"
        )


def test_a_section_runs_past_comments_in_code_blocks_to_the_next_heading():
    """A `# comment` in a fenced block is not a heading (Issue #1234)."""
    text = (
        "## Install\n\n"
        "### Installing only some Skills\n\n"
        "```bash\n"
        "# install one Skill\n"
        "npx skills add wikicommit/wikicommit --skill wikicommit-ask\n"
        "```\n\n"
        "~~~~\n"
        "## not a heading either\n"
        "~~~\n"
        "### still inside the tilde fence\n"
        "~~~~\n\n"
        "| Skill | Also install |\n"
        "|---|---|\n"
        "| `wikicommit-generate` | `wikicommit-init` |\n"
        "| `wikicommit-update` | `wikicommit-init` |\n\n"
        "#### A sub-heading stays in the section\n\n"
        "| `wikicommit-merge` | `wikicommit-init` |\n\n"
        "## Next section\n\n"
        "| `wikicommit-ask` | `wikicommit-init` |\n"
    )
    section = markdown_section(text, "### Installing only some Skills")
    assert table_rows(section, "demo") == {
        "wikicommit-generate": {"wikicommit-init"},
        "wikicommit-update": {"wikicommit-init"},
        "wikicommit-merge": {"wikicommit-init"},
    }
    assert "## Next section" not in section


def test_a_section_stops_at_a_higher_heading_and_ignores_fenced_lookalikes():
    text = (
        "```\n#### Skill 間の依存\n```\n"
        "#### Skill 間の依存\n"
        "| `wikicommit-a` | `wikicommit-b` |\n"
        "## §11.4\n"
        "| `wikicommit-c` | `wikicommit-d` |\n"
    )
    section = markdown_section(text, "#### Skill 間の依存")
    assert section == "#### Skill 間の依存\n| `wikicommit-a` | `wikicommit-b` |\n"
    with pytest.raises(ValueError, match="heading not found"):
        markdown_section("```\n### Only fenced\n```\n", "### Only fenced")


def test_a_line_opening_with_inline_code_is_not_a_fence():
    text = "### Target\n```x``` is inline code\n| `wikicommit-a` | `wikicommit-b` |\n### Next\n"
    assert markdown_section(text, "### Target") == (
        "### Target\n```x``` is inline code\n| `wikicommit-a` | `wikicommit-b` |\n"
    )
