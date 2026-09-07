"""Tests for .wikicommit/scripts/build_survey_view.py"""

import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / ".wikicommit" / "scripts" / "build_survey_view.py"
TEMPLATE_SCRIPT = (
    Path(__file__).parent.parent
    / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates" / "scripts" / "build_survey_view.py"
)


def run(cwd: Path, args: list[str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + (args or []),
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )


def write_config(root: Path, primary_lang: str = "ja") -> None:
    config_dir = root / ".wikicommit"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(
        f"translation:\n  primary_lang: {primary_lang}\n  targets: []\n", encoding="utf-8"
    )


def write_page(root: Path, lang: str, type_name: str, slug: str, frontmatter: str, body: str = "Body.\n") -> Path:
    page_dir = root / ".wikicommit" / "entity" / lang / type_name
    page_dir.mkdir(parents=True, exist_ok=True)
    page = page_dir / f"{slug}.md"
    page.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return page


def fm(title: str, lang: str = "ja", type_name: str = "Person", extra: str = "") -> str:
    return textwrap.dedent(f"""\
        title: "{title}"
        lang: {lang}
        type: "schema:{type_name}"
        """) + extra


def test_emits_one_record_per_page_with_title_type_tags_and_links(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        fm("山田太郎", extra="tags: [engineer, ml]\nproperties:\n  description: シニアエンジニア。\n"),
        body="## 経歴\n\n[[Place/tokyo]] に住む。\n\n## 業績\n\nBody.\n",
    )
    write_page(tmp_path, "ja", "Place", "tokyo", fm("東京", type_name="Place"))

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SURVEY: pages=2, types=2, lang=ja, all_langs=ja" in result.stdout
    assert "PAGE: Person/taro | 山田太郎 | backlinks=0 | tags=engineer,ml | links=Place/tokyo" in result.stdout
    assert "  DESC: シニアエンジニア。" in result.stdout
    assert "  HEADINGS: 経歴 / 業績" in result.stdout
    assert "TYPE: Person 1" in result.stdout
    assert "TAG: engineer 1" in result.stdout


def test_backlinks_counted_per_key_and_exclude_self_links(tmp_path):
    """A WikiLink carries no language, so a page and its translations are one
    node; a page's link to itself is not a backlink to itself."""
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "tokyo", fm("東京", type_name="Place"), body="[[Place/tokyo]]\n")
    write_page(tmp_path, "ja", "Person", "taro", fm("太郎"), body="[[Place/tokyo]]\n")
    write_page(
        tmp_path, "en", "Person", "taro", fm("Taro", lang="en"),
        body="[[Place/tokyo]]\n",
    )

    result = run(tmp_path)
    assert result.returncode == 0
    assert "HUB: Place/tokyo 1" in result.stdout


def test_lists_primary_lang_only_by_default_but_graph_spans_all_languages(tmp_path):
    """Translations restate the same content, so listing them mostly costs
    context — but dropping their links would undercount every hub."""
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", fm("東京", type_name="Place"))
    write_page(tmp_path, "en", "Person", "hanako", fm("Hanako", lang="en"), body="[[Place/tokyo]]\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "PAGE: Person/hanako" not in result.stdout
    assert "all_langs=en,ja" in result.stdout
    assert "HUB: Place/tokyo 1" in result.stdout


def test_lang_all_lists_every_language(tmp_path):
    write_config(tmp_path, primary_lang="ja")
    write_page(tmp_path, "ja", "Place", "tokyo", fm("東京", type_name="Place"))
    write_page(tmp_path, "en", "Person", "hanako", fm("Hanako", lang="en"))

    result = run(tmp_path, ["--lang", "all"])
    assert result.returncode == 0
    assert "PAGE: Person/hanako" in result.stdout
    assert "PAGE: Place/tokyo" in result.stdout


def test_removed_and_index_pages_are_excluded(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", fm("太郎"))
    write_page(
        tmp_path, "ja", "Person", "hanako",
        fm("花子", extra='status: removed\nremoved_at: "2026-01-01"\n'),
    )
    write_page(tmp_path, "ja", "Person", "index", fm("Person"), body="[[Person/taro]]\n")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SURVEY: pages=1" in result.stdout
    assert "PAGE: Person/hanako" not in result.stdout
    assert "PAGE: Person/index" not in result.stdout
    # The index links to every page of its type, so counting it would make
    # every page look referenced.
    assert "HUB:" not in result.stdout


def test_headings_inside_fenced_code_blocks_are_not_sections(tmp_path):
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro", fm("太郎"),
        body="## 本物の見出し\n\n```sh\n## これはコメント\n```\n\n## もう一つ\n",
    )

    result = run(tmp_path)
    assert result.returncode == 0
    assert "  HEADINGS: 本物の見出し / もう一つ" in result.stdout


def test_multiline_description_collapses_to_one_line(tmp_path):
    """Every record is one line, so an embedded newline would split it into two
    malformed ones."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        fm("太郎", extra="properties:\n  description: |\n    一行目。\n    二行目。\n"),
    )

    result = run(tmp_path)
    assert result.returncode == 0
    assert "  DESC: 一行目。 二行目。" in result.stdout


def test_scalar_tags_value_does_not_become_one_tag_per_character(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", fm("太郎", extra="tags: engineer\n"))

    result = run(tmp_path)
    assert result.returncode == 0
    assert "TAG: e " not in result.stdout
    assert "tags= |" in result.stdout or "| tags= |" in result.stdout


def test_max_pages_truncates_most_linked_first_and_says_so(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Place", "hub", fm("ハブ", type_name="Place"))
    for i in range(3):
        write_page(tmp_path, "ja", "Person", f"p{i}", fm(f"P{i}"), body="[[Place/hub]]\n")

    result = run(tmp_path, ["--max-pages", "2"])
    assert result.returncode == 0
    assert "SURVEY: pages=2" in result.stdout
    assert "TRUNCATED: 2 more page(s) not listed" in result.stdout
    # The most-linked page survives the cut; an alphabetical slice would drop it.
    assert "PAGE: Place/hub" in result.stdout


def test_unreadable_frontmatter_warns_without_failing(tmp_path):
    write_config(tmp_path)
    write_page(tmp_path, "ja", "Person", "taro", fm("太郎"))
    broken = tmp_path / ".wikicommit" / "entity" / "ja" / "Person" / "broken.md"
    broken.write_text("---\ntitle: [unclosed\n---\n\nBody.\n", encoding="utf-8")

    result = run(tmp_path)
    assert result.returncode == 0
    assert "WARNING" in result.stderr
    assert "SURVEY: pages=1" in result.stdout


def test_empty_wiki_exits_zero(tmp_path):
    write_config(tmp_path)

    result = run(tmp_path)
    assert result.returncode == 0
    assert "SURVEY: pages=0" in result.stdout


# ── Template sync (Issue #71-style drift guard) ───────────────────────────────────

def test_template_copy_matches_canonical_script():
    assert TEMPLATE_SCRIPT.read_text(encoding="utf-8") == SCRIPT.read_text(encoding="utf-8")


def test_pipe_in_title_or_tag_does_not_look_like_another_field(tmp_path):
    """`PAGE:` records are " | "-delimited, so a title of "A | B" must not read
    as two columns to the LLM consuming this."""
    write_config(tmp_path)
    write_page(
        tmp_path, "ja", "Person", "taro",
        fm("A | B", extra='tags: ["x|y"]\n'),
    )

    result = run(tmp_path)
    assert result.returncode == 0
    assert "PAGE: Person/taro | A / B | backlinks=0 | tags=x/y | links=" in result.stdout
