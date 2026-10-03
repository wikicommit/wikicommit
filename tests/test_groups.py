"""Tests for page groups (Issue #1035): _groups.py, check_groups.py, and the two
publish-side readers (rebuild_index.py, convert_wikilinks.py).

The point of keeping groups in `.wikicommit/groups/` is that grouping is not a
content change: grouping 40 pages must not move one byte of any page, or every
`reviewed` page would go back to `pending` (Issue #724). That property is the
first thing pinned here.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / ".wikicommit" / "scripts"


def run(root: Path, script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True, cwd=root
    )


def page(root: Path, lang: str, type_name: str, slug: str, extra: str = "") -> Path:
    path = root / ".wikicommit" / "entity" / lang / type_name / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\ntitle: "{slug}"\nlang: {lang}\ntype: "schema:{type_name}"\n'
        f"review_status: reviewed\n{extra}---\n\nBody of {slug}.\n",
        encoding="utf-8",
    )
    return path


def groups(root: Path, type_name: str, text: str) -> Path:
    path = root / ".wikicommit" / "groups" / f"{type_name}.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


GROUPS = """\
groups:
  practice:
    label: {ja: 実践・手法, en: Practices}
    criterion: "Something the reader does"
    pages: [vibe-coding, spec-driven]
  phenomenon:
    label: {en: Phenomena}
    pages: [context-rot]
"""


def wiki(root: Path) -> list[Path]:
    pages = [
        page(root, "en", "DefinedTerm", slug)
        for slug in ("vibe-coding", "spec-driven", "context-rot", "loose-one")
    ]
    pages.append(page(root, "ja", "DefinedTerm", "vibe-coding", "translated_from: x\n"))
    return pages


def digest(paths: list[Path]) -> list[str]:
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]


def test_grouping_never_touches_a_page(tmp_path):
    pages = wiki(tmp_path)
    before = digest(pages)
    groups(tmp_path, "DefinedTerm", GROUPS)
    assert run(tmp_path, "rebuild_index.py").returncode == 0
    out = tmp_path / "content"
    assert run(tmp_path, "convert_wikilinks.py", "--source", ".wikicommit/entity", "--output", str(out)).returncode == 0
    assert run(tmp_path, "check_groups.py").returncode == 0
    assert digest(pages) == before
    for p in pages:
        assert "review_status: reviewed" in p.read_text(encoding="utf-8")


def test_index_is_split_by_group_with_unclassified_last(tmp_path):
    wiki(tmp_path)
    groups(tmp_path, "DefinedTerm", GROUPS)
    run(tmp_path, "rebuild_index.py")
    body = (tmp_path / ".wikicommit/entity/en/DefinedTerm/index.md").read_text(encoding="utf-8").split("---\n", 2)[2]
    assert body == (
        "\n## Practices\n\n- [[DefinedTerm/spec-driven]]\n- [[DefinedTerm/vibe-coding]]\n\n"
        "## Phenomena\n\n- [[DefinedTerm/context-rot]]\n\n"
        "## Unclassified\n\n- [[DefinedTerm/loose-one]]\n"
    )
    ja = (tmp_path / ".wikicommit/entity/ja/DefinedTerm/index.md").read_text(encoding="utf-8")
    # The label follows the index's language; an empty group is left out.
    assert "## 実践・手法\n\n- [[DefinedTerm/vibe-coding]]\n" in ja
    assert "Phenomena" not in ja and "未分類" not in ja


def test_no_group_file_keeps_the_flat_index(tmp_path):
    wiki(tmp_path)
    run(tmp_path, "rebuild_index.py")
    index = (tmp_path / ".wikicommit/entity/en/DefinedTerm/index.md").read_text(encoding="utf-8")
    assert "##" not in index
    assert "- [[DefinedTerm/loose-one]]\n" in index


def test_invalid_group_file_falls_back_to_flat_and_is_reported(tmp_path):
    wiki(tmp_path)
    groups(tmp_path, "DefinedTerm", "groups:\n  a:\n    pages: [vibe-coding]\n  b:\n    pages: [vibe-coding]\n")
    result = run(tmp_path, "rebuild_index.py")
    assert "WARNING: groups file for DefinedTerm is invalid" in result.stdout
    assert "##" not in (tmp_path / ".wikicommit/entity/en/DefinedTerm/index.md").read_text(encoding="utf-8")
    report = run(tmp_path, "check_groups.py")
    assert report.returncode == 0
    assert "page `vibe-coding` is in both `a` and `b`" in report.stdout
    assert "errors=1" in report.stdout


def test_check_groups_counts_unclassified_and_stale(tmp_path):
    wiki(tmp_path)
    groups(tmp_path, "DefinedTerm", GROUPS + "  gone:\n    pages: [deleted-page]\n")
    page(tmp_path, "en", "Person", "someone")  # a Type with no group file is not reported
    result = run(tmp_path, "check_groups.py")
    assert "TYPE: DefinedTerm groups=3, grouped=3, unclassified=1, stale=1" in result.stdout
    assert "Person" not in result.stdout
    assert "SUMMARY: types=1, unclassified=1, stale=1, errors=0" in result.stdout

    detail = run(tmp_path, "check_groups.py", "--type", "DefinedTerm")
    assert "UNCLASSIFIED: .wikicommit/entity/en/DefinedTerm/loose-one.md" in detail.stdout
    assert "STALE_MEMBER: deleted-page (group gone)" in detail.stdout
    assert "GROUP: practice | pages=2" in detail.stdout


def test_check_groups_type_without_file_lists_everything_with_limit(tmp_path):
    wiki(tmp_path)
    detail = run(tmp_path, "check_groups.py", "--type", "DefinedTerm", "--limit", "2")
    assert "does not exist" in detail.stdout
    assert detail.stdout.count("UNCLASSIFIED:") == 2
    assert "TRUNCATED: 2 more" in detail.stdout
    # The primary-language copy is the one listed for a page that has translations.
    assert "/ja/" not in detail.stdout


def test_manifest_publishes_membership_under_published_slugs(tmp_path):
    wiki(tmp_path)
    groups(tmp_path, "DefinedTerm", GROUPS)
    out = tmp_path / "content"
    run(tmp_path, "convert_wikilinks.py", "--source", ".wikicommit/entity", "--output", str(out))
    manifest = json.loads((out / "wikicommit-groups.json").read_text(encoding="utf-8"))
    assert manifest["folders"]["en/definedterm"] == {
        "groups": {"practice": "Practices", "phenomenon": "Phenomena"},
        "pages": {"vibe-coding": "practice", "spec-driven": "practice", "context-rot": "phenomenon"},
    }
    assert manifest["folders"]["ja/definedterm"]["groups"] == {"practice": "実践・手法"}
    # The published page itself is unchanged by grouping: same path, no new field.
    assert (out / "en/DefinedTerm/vibe-coding.md").exists()
    assert "group" not in (out / "en/DefinedTerm/vibe-coding.md").read_text(encoding="utf-8").split("---")[1]


def test_manifest_is_absent_without_groups_and_removed_when_they_go(tmp_path):
    wiki(tmp_path)
    out = tmp_path / "content"
    args = ("--source", ".wikicommit/entity", "--output", str(out))
    run(tmp_path, "convert_wikilinks.py", *args)
    assert not (out / "wikicommit-groups.json").exists()
    gf = groups(tmp_path, "DefinedTerm", GROUPS)
    run(tmp_path, "convert_wikilinks.py", *args)
    assert (out / "wikicommit-groups.json").exists()
    gf.unlink()
    run(tmp_path, "convert_wikilinks.py", *args)
    assert not (out / "wikicommit-groups.json").exists()


def test_custom_type_group_file_keeps_its_segment(tmp_path):
    page(tmp_path, "en", "custom/Decision", "pick-a")
    groups(tmp_path, "custom/Decision", "groups:\n  early:\n    pages: [pick-a]\n")
    assert "TYPE: custom/Decision groups=1, grouped=1, unclassified=0" in run(tmp_path, "check_groups.py").stdout
    out = tmp_path / "content"
    run(tmp_path, "convert_wikilinks.py", "--source", ".wikicommit/entity", "--output", str(out))
    manifest = json.loads((out / "wikicommit-groups.json").read_text(encoding="utf-8"))
    # Published with the custom/ segment flattened away (Issue #576).
    assert manifest["folders"]["en/decision"]["pages"] == {"pick-a": "early"}
