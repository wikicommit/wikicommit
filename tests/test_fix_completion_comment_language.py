"""`/wikicommit-fix` Step 7's completion comment follows the page, not the wiki (Issue #824).

Issue #808 moved that comment off a hard-coded Japanese string and onto
`primary_lang`, reasoning that a reporter who read the page can read the
language it is written in. The premise was right; the target was not. A
reporter reads *one page*, and a page's banner and report link render in that
page's own `lang` (Issue #378) — so on a `primary_lang: ja` wiki with
`targets: [en]`, `primary_lang` sends an English reader a Japanese reply about
an Issue that only they can close. The two values are identical when `targets`
is empty, which is why the gap was invisible where #808 was looking.

These tests pin the decision because it lives only in Skill prose, and because
the wrong answer is the *plausible* one: `primary_lang` is what the neighbouring
tracking-Issue rule uses (Issue #773), and reading that across is exactly the
mistake the prose now warns about. Nothing else in the repo would notice the
rule sliding back.

They check that the decision is stated, that its two hardest edges are stated
with it (Step 4's redirect does not move the reader; the report's own text is
not used to infer a language), and that Step 5's `translator_notes` still
writes in the page's own `lang` — that last one is what makes the Skill give
one answer instead of two.
"""

from pathlib import Path

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
FIX_SKILL = (SKILLS / "wikicommit-fix" / "SKILL.md").read_text(encoding="utf-8")


def _step7() -> str:
    """Step 7's body — the language rule must live there, not merely somewhere."""
    start = FIX_SKILL.index("### Step 7: Link Back to the Originating Issue")
    end = FIX_SKILL.index("## Notes", start)
    return FIX_SKILL[start:end]


def _step5() -> str:
    """Step 5's body, scoped for the same reason `_step7()` is.

    Step 7 now discusses `translator_notes` by name, so an unscoped search of
    the whole file could be satisfied by prose *about* the rule while the rule
    itself had moved to `primary_lang`.
    """
    start = FIX_SKILL.index("### Step 5: User Confirmation → Write")
    end = FIX_SKILL.index("### Step 6: Report Results", start)
    return FIX_SKILL[start:end]


def test_step7_renders_in_the_target_pages_lang():
    step7 = _step7()
    assert "**Render this comment in the `lang` of the target page identified in Step 2**" in step7, (
        "wikicommit-fix Step 7 no longer renders the completion comment in the "
        "language of the page the reporter read (Issue #824)."
    )
    assert "**Render this comment in the wiki's `primary_lang`**" not in step7, (
        "wikicommit-fix Step 7 has gone back to rendering the completion comment "
        "in primary_lang, which does not reach a reporter who read a translated "
        "page (Issue #824 replaced Issue #808's rule here)."
    )


def test_step7_no_longer_records_the_language_as_undecided():
    """Issue #808 left the gap open on purpose; #824 closed it.

    The old wording called this "a real gap and not a settled case" and told the
    reader to use `primary_lang` until it was decided. Leaving that in place
    beside the decision would read as if the decision were still pending.
    """
    step7 = _step7()
    assert "a real gap and not a settled case" not in step7, (
        "wikicommit-fix Step 7 still describes its comment language as undecided "
        "(Issue #824 decided it)."
    )


def test_step7_states_that_the_redirect_does_not_change_the_language():
    """The fix can land on a page the reporter never read (Issue #529).

    Without this, "the target page's `lang`" is ambiguous in the one case where
    the two candidate pages actually differ.
    """
    step7 = _step7()
    assert "**Step 4's redirect does not change this.**" in step7, (
        "wikicommit-fix Step 7 no longer says which page's `lang` applies when a "
        "content-derived point was redirected to the original page (Issue #824)."
    )


def test_step7_refuses_to_infer_the_language_from_the_report():
    """A judgement call must not displace a deterministic answer.

    The report's own text is stronger evidence than the page, but it is not
    always present (a proper noun and a URL carry no signal), so making the
    comment's language depend on it would trade a deterministic rule for one
    that silently varies.
    """
    step7 = _step7()
    assert "**Do not infer the language from the report's own text.**" in step7, (
        "wikicommit-fix Step 7 no longer rules out inferring the comment's "
        "language from the report itself (Issue #824, 検討事項 1)."
    )


def test_translator_notes_still_follow_the_pages_own_lang():
    """Step 5 item 5 is the other place this Skill picks a language (Issue #524).

    It already wrote in the page's own `lang`. If that ever moved to
    `primary_lang`, the Skill would again give two answers to one rule — which
    is the asymmetry Issue #824 was filed about.
    """
    assert "the translation's language, not `primary_lang`" in _step5(), (
        "wikicommit-fix Step 5 no longer writes translator_notes in the target "
        "page's own lang, so the Skill answers the same question two ways "
        "(Issue #524 / #824)."
    )


def test_step7_prefers_the_report_links_own_language_line():
    """Step 2 does not resolve the read page on the banner-report route.

    The report link (Issue #245) prefills the body with a published `Page:` URL
    and a `Language:` line, not a `.wikicommit/entity/` path — so Step 2 skips
    its first branch and keyword-searches, and that search merges a page with
    its translations into one row. On a `primary_lang: ja` wiki with
    `targets: [en]` the Issue can resolve to the `ja` original, and keying the
    comment off the Step 2 page alone would reproduce the very failure this
    rule exists to prevent.
    """
    step7 = _step7()
    assert "**When the Issue was filed through a published page's report link, its body names the page's language outright — use that in preference to the Step 2 page.**" in step7, (
        "wikicommit-fix Step 7 no longer prefers the report link's own `Language:` "
        "line, so an Issue filed from a translated page can still be answered in "
        "the original page's language (Issue #824)."
    )
    assert "**This bars reading the reporter's own prose, not the banner's `Language:` line**" in step7, (
        "wikicommit-fix Step 7's 'do not infer the language' rule no longer "
        "excludes the banner's machine-emitted `Language:` line, so it reads as "
        "banning the one deterministic signal available (Issue #824)."
    )


def test_step7_matches_the_report_labels_in_both_banner_locales():
    """The banner writes those labels in the page's own locale, not in English.

    A report filed from a `ja` page reads `言語: ja`, so matching only
    `Language:` would miss exactly the pages this rule is for — and mirror the
    original failure onto a `primary_lang: en` wiki with `targets: [ja]`. The
    banner ships two locales and falls back to English for any third language
    (Issue #823), so the four spellings below are the whole set.
    """
    step7 = _step7()
    for label in ("`Language:` / `言語:`", "`Page:` / `ページ:`"):
        assert label in step7, (
            f"wikicommit-fix Step 7 no longer matches {label} in both of the "
            "banner's locales, so a report filed from a page in the other one "
            "falls through to the keyword search (Issue #824)."
        )
