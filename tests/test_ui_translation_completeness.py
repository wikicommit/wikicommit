"""Every WikiCommit UI translation says the same shape of thing as the English (Issue #1017).

WikiCommit's own UI strings — the four Quartz plugins' locale files and
convert_wikilinks.py's four *_LABELS dicts — ship ten languages, the nine
non-English ones produced by an LLM from the English. Nobody here reads all
nine, so what can be checked mechanically is checked here:

- **Keys.** A locale file missing a key does not compile, and a dict entry
  missing one raises KeyError at build time; both are caught, but only by a
  build nobody runs in this repository's CI for the dicts. This test catches
  the dict case first and names the key.
- **Placeholders.** `{pages}`, `{reviewed}`, `{name}` and the rest are filled
  by `str.format` / string replacement. A dropped one silently loses a number;
  a misspelled one raises KeyError at build time.
- **Markdown markers.** A value that is a heading (`## `) or a list item
  (`- `) in English has to stay one, and bold spans have to stay balanced.

What it cannot check is whether a translation claims more than the English —
that is why the source comments say the English is canonical.
"""

import ast
import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).parent.parent / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
PLUGINS = TEMPLATES / "quartz-plugins"
CONVERT = TEMPLATES / "scripts" / "convert_wikilinks.py"
PLUGIN_NAMES = ("wikicommit-banner", "wikicommit-sources", "wikicommit-properties", "wikicommit-language-switcher")
LABEL_DICTS = ("ROOT_INDEX_LABELS", "SOURCE_TYPE_LABELS", "SOURCE_PAGE_LABELS", "OVERVIEW_LABELS")
EXPECTED_LANGS = {"ja", "de", "es", "fr", "it", "pl", "pt", "ru", "zh"}
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
# A locale file is `export default { components: { <name>: { key: "value", ... } } }`
# with one key per entry; a value is one JSON-style double-quoted string, on the
# key's line or (when long) on the next.
ENTRY = re.compile(r'^\s*([A-Za-z0-9_]+):\s*("(?:[^"\\]|\\.)*"),?\s*$', re.MULTILINE)


def _locale_entries(path: Path) -> dict[str, str]:
    source = re.sub(r"^\s*//.*$", "", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    return {k: ast.literal_eval(v) for k, v in ENTRY.findall(source)}


def _label_dicts() -> dict[str, tuple[dict, dict]]:
    tree = ast.parse(CONVERT.read_text(encoding="utf-8"))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            values[node.targets[0].id] = node.value
    return {name: (ast.literal_eval(values[name]), ast.literal_eval(values[f"DEFAULT_{name}"])) for name in LABEL_DICTS}


def _shape_mismatches(english: str, translated: str) -> list[str]:
    problems = []
    if sorted(PLACEHOLDER.findall(english)) != sorted(PLACEHOLDER.findall(translated)):
        problems.append(f"placeholders {PLACEHOLDER.findall(english)} vs {PLACEHOLDER.findall(translated)}")
    for marker in ("## ", "- "):
        if english.startswith(marker) != translated.startswith(marker):
            problems.append(f"leading {marker!r}")
    if english.count("**") != translated.count("**"):
        problems.append("bold markers")
    return problems


@pytest.mark.parametrize("plugin", PLUGIN_NAMES)
def test_every_plugin_locale_matches_en_us(plugin):
    locales_dir = PLUGINS / plugin / "src" / "i18n" / "locales"
    english = _locale_entries(locales_dir / "en-US.ts")
    assert english, f"could not read {plugin}'s en-US.ts"
    others = [p for p in sorted(locales_dir.glob("*.ts")) if p.name != "en-US.ts"]
    assert {p.stem.split("-")[0] for p in others} == EXPECTED_LANGS, (
        f"{plugin} ships {sorted(p.stem for p in others)} besides en-US; the set is "
        "the ten Wikipedia-portal languages (Issue #1017)."
    )
    for path in others:
        translated = _locale_entries(path)
        assert set(translated) == set(english), (plugin, path.name, set(translated) ^ set(english))
        for key, value in english.items():
            problems = _shape_mismatches(value, translated[key])
            assert not problems, f"{plugin} {path.name} {key}: {problems}"


@pytest.mark.parametrize("dict_name", LABEL_DICTS)
def test_every_label_dict_entry_matches_the_default(dict_name):
    entries, default = _label_dicts()[dict_name]
    assert set(entries) == EXPECTED_LANGS, (dict_name, sorted(entries))
    for lang, labels in entries.items():
        assert set(labels) == set(default), (dict_name, lang, set(labels) ^ set(default))
        for key, value in default.items():
            problems = _shape_mismatches(value, labels[key])
            assert not problems, f"{dict_name}[{lang!r}][{key!r}]: {problems}"
