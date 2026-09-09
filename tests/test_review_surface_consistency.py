"""The three reader-facing surfaces that count human review must stay in step (Issue #800).

Every Issue in the review-display chain — #663 (name the reviewer), #705 (drop
a stale name), #774 (the heading stops swapping), #769 (the AI count reaches the
root index) — was filed because **one surface disagreed with another**, never
because the definition itself needed rethinking. #769 is the clearest case: #751
put the AI count on the overview page and forgot the root index, and a day later
that cost an Issue, a PR and a changelog entry.

The drift has a structural cause. The root index and overview labels are Python
dicts in `convert_wikilinks.py`; the banner's are TypeScript in `ja-JP.ts` /
`en-US.ts`. **Nothing looks at both**, so a change made in one language or on one
surface is invisible from the other until a reader sees the mismatch.

What these tests check is *structure only* — that the same keys exist on both
sides of each pair, and that every surface that prints a human-review count also
carries the note qualifying it. They do not check wording, and they cannot catch
a change that is wrong on every surface at once. That is the intended scope: the
failure being prevented is the one-sided update.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES = REPO_ROOT / ".claude" / "skills" / "wikicommit-init" / "scripts" / "templates"
CONVERT = (TEMPLATES / "scripts" / "convert_wikilinks.py").read_text(encoding="utf-8")
BANNER_LOCALES = TEMPLATES / "quartz-plugins" / "wikicommit-banner" / "src" / "i18n" / "locales"


def _balanced(text: str) -> str:
    """`text` from its first `{` up to the `}` that closes it.

    The label values carry `{pages}` / `{reviewed}` placeholders, but those are
    balanced pairs, so counting braces still lands on the right one.
    """
    depth = 0
    for i, ch in enumerate(text):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[:i]
    return text


def _dict_block(source: str, name: str, *, nested_lang: str | None = None) -> str:
    """The text of a top-level dict literal in the script.

    Parsed textually rather than by importing: `convert_wikilinks.py` is a
    distributed script with its own imports, and this test only needs the shape
    of two literals. A nested dict (`ROOT_INDEX_LABELS["ja"]`) can be read
    without pulling in the outer one.
    """
    block = _balanced(source[source.index(f"{name} = {{") :])
    if nested_lang is not None:
        block = _balanced(block[block.index(f'"{nested_lang}": {{') :])
    return block


def _strip_comments(block: str) -> str:
    """`block` with whole comment lines removed.

    The label dicts carry their design rationale as `#` comments, and that
    rationale is allowed words the strings themselves are not (the `counts_ai`
    comment calls the human number "the sample taken out of it"). None of these
    dicts uses a trailing comment, so dropping whole comment lines is enough and
    does not need a Python parser.
    """
    return "\n".join(
        line for line in block.split("\n") if not line.lstrip().startswith("#")
    )


def _dict_keys(source: str, name: str, *, nested_lang: str | None = None) -> set[str]:
    """The string keys of a dict literal, matched at their own indentation."""
    block = _dict_block(source, name, nested_lang=nested_lang)
    return set(re.findall(r'^\s{4,}"([a-z_]+)":', block, re.M))


def _joined(source: str) -> str:
    """Adjacent string literals joined, so a phrase split across a wrapped
    literal is still found.

    Both files wrap long notes across lines, and where the break falls is a
    formatting choice with no meaning. Searching the raw text would make these
    assertions depend on it — the note would "disappear" from a file that still
    emits it, which is a false failure of exactly the kind that trains people to
    ignore a check.
    """
    return re.sub(r'"\s*\n\s*"', "", source)


def _banner_keys(locale_file: str) -> set[str]:
    source = (BANNER_LOCALES / locale_file).read_text(encoding="utf-8")
    return set(re.findall(r"^\s+([a-zA-Z]+):\s", source, re.M))


def test_root_index_labels_have_the_same_keys_in_both_languages():
    """A key added to only one of the two ships a language with a blank line
    where the other has a sentence — and `convert_wikilinks.py` falls back to
    the default set per key, so nothing raises."""
    ja = _dict_keys(CONVERT, "ROOT_INDEX_LABELS", nested_lang="ja")
    default = _dict_keys(CONVERT, "DEFAULT_ROOT_INDEX_LABELS")
    assert ja == default, (
        "ROOT_INDEX_LABELS['ja'] and DEFAULT_ROOT_INDEX_LABELS disagree: "
        f"ja-only={sorted(ja - default)}, default-only={sorted(default - ja)}"
    )


def test_overview_labels_have_the_same_keys_in_both_languages():
    ja = _dict_keys(CONVERT, "OVERVIEW_LABELS", nested_lang="ja")
    default = _dict_keys(CONVERT, "DEFAULT_OVERVIEW_LABELS")
    assert ja == default, (
        "OVERVIEW_LABELS['ja'] and DEFAULT_OVERVIEW_LABELS disagree: "
        f"ja-only={sorted(ja - default)}, default-only={sorted(default - ja)}"
    )


def test_banner_locales_have_the_same_keys():
    ja = _banner_keys("ja-JP.ts")
    en = _banner_keys("en-US.ts")
    assert ja == en, (
        "The banner's ja-JP.ts and en-US.ts disagree: "
        f"ja-only={sorted(ja - en)}, en-only={sorted(en - ja)}"
    )


def test_every_surface_that_counts_human_review_also_qualifies_the_number():
    """The bare count reads as "nobody cares about this project" (Issue #664),
    and after Issue #800 it also has to say the number is partial by design.
    Each surface carries its own note key because word order and parenthesis
    style differ per language (Issues #730 / #769); what must not vary is that
    a surface printing the count has one.
    """
    root_ja = _dict_keys(CONVERT, "ROOT_INDEX_LABELS", nested_lang="ja")
    overview_ja = _dict_keys(CONVERT, "OVERVIEW_LABELS", nested_lang="ja")
    banner = _banner_keys("ja-JP.ts")

    assert {"counts", "counts_note"} <= root_ja, (
        "The root index prints a human-review count without the note that "
        "qualifies it (Issue #664 / #800)."
    )
    assert {"reviewed", "reviewed_note"} <= overview_ja, (
        "The overview page prints a human-review count without its note."
    )
    assert {"siteSummaryReviewed", "siteSummaryReviewNote"} <= banner, (
        "The banner's site summary prints a human-review count without its note."
    )


def test_all_three_notes_say_the_human_number_is_partial_by_design():
    """The substance Issue #800 added, asserted per surface.

    This is the one wording check here, and it exists because the three notes
    are three separate strings by deliberate choice (Issues #730 / #769 kept
    them un-shared, since assembling them from fragments breaks per-language
    word order). Three copies of a claim is exactly the shape that drifts.
    """
    banner_ja = (BANNER_LOCALES / "ja-JP.ts").read_text(encoding="utf-8")
    banner_en = (BANNER_LOCALES / "en-US.ts").read_text(encoding="utf-8")

    for label, source, phrase in [
        ("convert_wikilinks.py (ja)", _joined(CONVERT), "人による確認は設計上一部のページのみ"),
        ("convert_wikilinks.py (en)", _joined(CONVERT), "Only some pages are read by a person, by design"),
        ("banner ja-JP.ts", _joined(banner_ja), "人による確認は設計上一部のページのみ"),
        ("banner en-US.ts", _joined(banner_en), "Only some pages are read by a person, by design"),
    ]:
        assert phrase in source, (
            f"{label} no longer says the human-review count is partial by "
            "design, so the number reads as a backlog rather than as the "
            "design it is (Issue #800)."
        )
    # Both notes in convert_wikilinks.py (root index and overview), not just one.
    assert _joined(CONVERT).count("人による確認は設計上一部のページのみ") == 2, (
        "Only one of the root index's and the overview page's Japanese notes "
        "says the count is partial by design."
    )
    assert _joined(CONVERT).count("Only some pages are read by a person, by design") == 2, (
        "Only one of the root index's and the overview page's English notes "
        "says the count is partial by design."
    )


def test_reader_facing_copy_avoids_sampling_vocabulary():
    """Issue #769's constraint, which Issue #800 works within rather than around.

    Saying the number is partial by design is not the same as calling it a
    sample: whether `RISKY:` actually selects well is unmeasured, and the word
    alone would imply a formal sampling design exists. The design record uses
    the word freely; reader-facing strings do not.
    """
    banner_ja = (BANNER_LOCALES / "ja-JP.ts").read_text(encoding="utf-8")
    banner_en = (BANNER_LOCALES / "en-US.ts").read_text(encoding="utf-8")
    # The root index and the overview page are covered too: Issue #769 made this
    # ruling about their counts in the first place, so a guard that only watched
    # the banner would leave the surfaces it was written for unwatched.
    sources = [
        ("banner ja-JP.ts", banner_ja),
        ("banner en-US.ts", banner_en),
    ] + [
        (f"convert_wikilinks.py ({name})", _strip_comments(_dict_block(CONVERT, name)))
        for name in (
            "ROOT_INDEX_LABELS",
            "DEFAULT_ROOT_INDEX_LABELS",
            "OVERVIEW_LABELS",
            "DEFAULT_OVERVIEW_LABELS",
        )
    ]
    for label, source in sources:
        for word in ("sample", "Sample", "sampling", "抜取", "サンプリング"):
            assert word not in source, (
                f"{label} uses sampling vocabulary ({word!r}) in reader-facing "
                "copy (Issue #769)."
            )
