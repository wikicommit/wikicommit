"""Who is told that WikiCommit's own labels fell back to English (Issue #825).

WikiCommit writes its own labels in two languages. A wiki whose `primary_lang`
is neither gets its page bodies and Quartz's chrome in that language, and the
review banner, sources box, page properties and generated index/overview pages
in English. Issue #809 settled that this fallback is the right behaviour — an
unverifiable translation of a sentence that says what this wiki does *not*
vouch for fails invisibly, English fails visibly — and left one question open:
whether a reader should be told it happened.

Issue #825 answered no for readers and yes for the operator, once, at init. The
reasoning is recorded beside `ROOT_INDEX_LABELS`; what these tests hold is that
the two halves stay in place, because each is invisible from the other. The
notice is a `NOTE:` line in a script nobody reads twice, and the decision not to
publish anything is a comment — nothing fails if either quietly goes away, and
the failure mode is that a later change adds a reader-facing notice on the
grounds that the question was never settled, which is the state this Issue
found.
"""

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
INIT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "init.py"
TEMPLATES = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
CONVERT = (TEMPLATES / "scripts" / "convert_wikilinks.py").read_text(encoding="utf-8")
PLUGINS = TEMPLATES / "quartz-plugins"

# Every surface `ui_language_notice()` names, and how each one records which
# languages it has labels for. The notice claims all four render in English, so
# a language added to any one of them without `WIKICOMMIT_UI_LANGS` makes the
# notice say something untrue — checking only the three that happen to expose a
# `LANG_TO_LOCALE` leaves the easiest one to edit unguarded, since the
# `*_LABELS` dicts are plain Python with no compile-time completeness check
# behind them.
LANG_TO_LOCALE_PLUGINS = ("wikicommit-banner", "wikicommit-properties", "wikicommit-sources")
LOCALES_ONLY_PLUGINS = ("wikicommit-language-switcher",)
CONVERT_LABEL_DICTS = ("ROOT_INDEX_LABELS", "SOURCE_TYPE_LABELS", "SOURCE_PAGE_LABELS", "OVERVIEW_LABELS")


def _init_module():
    """Same loader `tests/test_init.py` uses; `init.py` imports a bare sibling."""
    sys.path.insert(0, str(INIT_SCRIPT.parent))
    try:
        spec = importlib.util.spec_from_file_location("wikicommit_init_for_i18n", INIT_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(INIT_SCRIPT.parent))
    return module


def _plugin_lang_to_locale_keys(plugin: str) -> set[str]:
    """The `lang` values a plugin's `LANG_TO_LOCALE` maps, read from the source.

    The plugins are TypeScript, so this reads the literal rather than executing
    it. The block is a flat `Record<string, string>` of `xx: "xx-YY",` lines,
    which is exactly what the comment above it tells an editor to add to.
    """
    source = (PLUGINS / plugin / "src" / "i18n" / "index.ts").read_text(encoding="utf-8")
    start = source.index("const LANG_TO_LOCALE")
    block = source[start : source.index("}", start)]
    return set(re.findall(r"^\s*(\w+):", block, re.MULTILINE))


def _plugin_locale_langs(plugin: str) -> set[str]:
    """The languages a plugin ships, for one that keys `locales` directly.

    `wikicommit-language-switcher` has no `LANG_TO_LOCALE` — it resolves
    `cfg.locale` straight against `locales`, whose keys are BCP 47 tags — so the
    language is the primary subtag of each key. It is still one of the four
    plugins its own comment says gain a locale together or not at all, so a
    third locale landing here alone has to fail rather than pass silently.
    """
    source = (PLUGINS / plugin / "src" / "i18n" / "index.ts").read_text(encoding="utf-8")
    start = source.index("const locales")
    block = source[start : source.index("}", start)]
    return {tag.split("-")[0] for tag in re.findall(r'^\s*"([\w-]+)":', block, re.MULTILINE)}


def _convert_label_langs(dict_name: str) -> set[str]:
    """The languages one of `convert_wikilinks.py`'s `*_LABELS` dicts covers.

    These back the generated index/overview and source pages — the fourth
    surface the notice names. English is not a key: it lives in the sibling
    `DEFAULT_*` dict, so it is added here rather than read. Parsed rather than
    imported because the template imports siblings that are not on the path.
    """
    for node in ast.parse(CONVERT).body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == dict_name
        ):
            assert isinstance(node.value, ast.Dict), f"{dict_name} is no longer a dict literal"
            return {"en"} | {key.value for key in node.value.keys}
    raise AssertionError(f"{dict_name} is gone from convert_wikilinks.py")


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_a_translated_language_prints_nothing(lang):
    """The common case has to stay silent, or the line stops being read."""
    assert _init_module().ui_language_notice(lang) is None, (
        f"init.py now prints a UI-language notice for {lang!r}, which WikiCommit "
        "does translate (Issue #825)."
    )


@pytest.mark.parametrize("lang", ["it", "fr", "IT", " it "])
def test_an_untranslated_language_is_disclosed_to_the_operator(lang):
    """Case and surrounding space must not decide whether the operator is told."""
    notice = _init_module().ui_language_notice(lang)
    assert notice is not None, (
        f"init.py no longer tells an operator choosing {lang!r} that WikiCommit's "
        "own labels will render in English — and the published pages deliberately "
        "say nothing either, so nobody is told at all (Issue #825)."
    )
    assert notice.startswith("NOTE:"), "the notice is informational, not an error or a warning"
    assert "English" in notice


def test_the_notice_says_what_does_not_fall_back():
    """"Everything is English" would be false and would read as a broken install.

    Page bodies and Quartz's own chrome do follow the chosen language — only
    WikiCommit's own additions fall back, and the split is not guessable.
    """
    notice = _init_module().ui_language_notice("it")
    assert "Page bodies" in notice and "Quartz" in notice, (
        "init.py's UI-language notice no longer distinguishes what still renders "
        "in the chosen language from what falls back (Issue #825)."
    )


def test_the_ui_language_set_matches_every_surface_the_notice_names():
    """`WIKICOMMIT_UI_LANGS` is a copy, and a copy that drifts tells a lie.

    `init.py` creates `.wikicommit/`, so it cannot import from the tree it is
    about to write. If a third locale is added to any of the surfaces the notice
    names and not here, the notice keeps claiming that language falls back when
    it no longer does — and the `*_LABELS` dicts are the likeliest place for
    that, being plain Python with no `Record<string, typeof enUS>` behind them
    refusing to compile a partial locale.
    """
    ui_langs = set(_init_module().WIKICOMMIT_UI_LANGS)
    surfaces = {
        **{f"{p}'s LANG_TO_LOCALE": _plugin_lang_to_locale_keys(p) for p in LANG_TO_LOCALE_PLUGINS},
        **{f"{p}'s locales": _plugin_locale_langs(p) for p in LOCALES_ONLY_PLUGINS},
        **{f"convert_wikilinks.py's {d}": _convert_label_langs(d) for d in CONVERT_LABEL_DICTS},
    }
    for surface, langs in surfaces.items():
        assert langs == ui_langs, (
            f"{surface} and init.py's WIKICOMMIT_UI_LANGS disagree about which "
            "languages WikiCommit has labels for, so the notice init.py prints is "
            f"wrong about {sorted(langs ^ ui_langs)} (Issue #825)."
        )


def test_convert_wikilinks_records_the_decision_rather_than_the_open_question():
    """The one place that held the question now has to hold the answer.

    Issue #809 wrote the question here and nowhere else. Left as "not settled",
    the next reader has to decide it again — and deciding it the other way adds
    a standing notice to every page of such a wiki.
    """
    assert "a separate\n# question that has not been settled" not in CONVERT, (
        "convert_wikilinks.py still records the fallback-disclosure question as "
        "open, though Issue #825 decided it."
    )
    assert "**The published pages do not say that the fallback happened**" in CONVERT, (
        "convert_wikilinks.py no longer states that the fallback is deliberately "
        "not disclosed to readers (Issue #825)."
    )
    assert "**The operator is told instead, once**" in CONVERT, (
        "convert_wikilinks.py no longer names who *is* told, which leaves the "
        "decision reading as 'nobody is told' (Issue #825)."
    )
