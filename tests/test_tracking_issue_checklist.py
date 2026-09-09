"""Tests for the human review checklist in the tracking-Issue template (Issue #723).

The three checklist variants `wikicommit-merge` Step 8 writes used to be the
same three questions `wikicommit-review` Step 4 asks, and two of those three —
does it match the source, are there hallucinations — are what Pass 4 already
checks with far more behind it. A human closing the Issue was walking a third
lap of a check the machine is better at, and the top rung of the trust ladder
was being signed on that basis.

What replaced them is not an arbitrary line. Pass 4's evidence-binding rule
(Issue #442) forbids the machine from judging on anything but the literal
source text, which makes outside knowledge the one kind of evidence only a
human can bring; and harm is checked by no layer at all
(`.wikicommit/entity-policy.md` decides whether a page gets written, never what
its sentences say). These tests hold that split in place: the checklists are
prose in a Skill file, so nothing else notices if an item is dropped or if the
"tell us if you know" wording drifts back into "go and research it" — which
would reintroduce on the human side exactly what Issue #722 rules out on the
machine side.

Issue #740 then changed the shape. `review_status` is a two-valued field, so
what it can carry is an *event* — this page was read, or it has not been — and
the claim it used to carry had to be bolted on as a checklist, which is what
made closing a signature. The checkboxes are gone; the Issue asks for one line
on what the reader took away, and the machine-blind areas follow as prompts.
The tests below moved with it. Three of them are new protections that only
matter under the new shape: that the ask for a line is there, that "this is not
a test" is written down beside it, and that the machine's own source check is
stated rather than re-asked — that last one is what stops the removal of the
source-fidelity items from reading as "nothing checked this page" (Issue #751
put that check on the page itself, which is why it lands in this order).
"""

import re
from pathlib import Path

import pytest

SKILLS = Path(__file__).parent.parent / ".claude" / "skills"
MERGE_SKILL = (SKILLS / "wikicommit-merge" / "SKILL.md").read_text(encoding="utf-8")
REVIEW_SKILL = (SKILLS / "wikicommit-review" / "SKILL.md").read_text(encoding="utf-8")

# Issue #740 replaced the checkbox list with a request for one line plus
# prompts, so there is no longer a marked/unmarked split to assert. What has to
# hold instead is that the machine's half is stated: without it, dropping the
# source-fidelity items reads as "no check ran at all".
MACHINE_HALF_PHRASE = "already checked"
LINE_ASK_PHRASE = "what you took away"
NOT_A_TEST_PHRASE = "not a test of your understanding"

# The shared section Step 8 inserts verbatim into every variant body.
SHARED_HOW_TO_PROCEED_HEADING = '##### Shared "How to Proceed" section (all variants)'

# The checklist bodies, split out of the Skill file by their variant headings so
# each variant can be asserted on separately. The headings are the ones Step 8's
# "Issue Body Template" section uses.
VARIANT_HEADINGS = [
    "##### `sources`-based pages (no `translated_from`, no `derived_from`)",
    "##### Translation pages (`translated_from` present)",
    "##### Synthesized pages (`derived_from` present)",
]


HEADING_RE = re.compile(r"#{1,6} ")


def variant_body(heading: str) -> str:
    """The section under `heading`, up to the next heading of any level.

    Bounding on the next `##### ` alone is not enough: the last variant is
    followed by `### Step 9`, so its body would run to the end of the file. The
    exclusion assertion below would then cover Steps 9-10 and Notes (failing on
    text with nothing to do with the checklist), and the inclusion assertions
    would pass for that variant even with its item deleted, as long as the
    phrase appeared anywhere further down.

    The scan has to skip fenced blocks, because the templates themselves
    contain `## Review Target` / `## Once You Have Read It` headings.
    """
    start = MERGE_SKILL.index(heading) + len(heading)
    body: list[str] = []
    in_fence = False
    for line in MERGE_SKILL[start:].split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and HEADING_RE.match(line):
            break
        body.append(line)
    return "\n".join(body)


@pytest.fixture(scope="module")
def variants() -> dict[str, str]:
    return {h: variant_body(h) for h in VARIANT_HEADINGS}


def test_every_variant_asks_the_harm_question(variants):
    """A harmful sentence is harmful whatever produced it, so this one goes in
    all three. It matters most on the synthesized variant, where every
    automated check compares single claims against grounding pages and none
    asks what several of them imply together (Issue #674)."""
    for heading, body in variants.items():
        assert "a real person or organization" in body, (
            f"The {heading!r} template no longer prompts for harm. No "
            "automated layer checks it: entity-policy.md decides whether a page "
            "is written, never what its sentences say."
        )


def test_only_the_sources_variant_asks_the_reviewer_what_they_know(variants):
    """On a translation a stale fact belongs to the original page, and on a
    synthesized page to whichever grounding page states it — the same redirect
    `wikicommit-fix` makes (Issue #529), and the reason the three variants
    exist at all (Issue #525)."""
    sources_body = variants[VARIANT_HEADINGS[0]]
    assert "conflicts with what you already know" in sources_body

    for heading in VARIANT_HEADINGS[1:]:
        assert "conflicts with what you already know" not in variants[heading], (
            f"The {heading!r} template now asks the reviewer for outside "
            "knowledge, but a fix prompted by it belongs on a different page — "
            "the original, or the grounding page that states the fact."
        )


def test_the_knowledge_item_does_not_ask_for_research():
    """"Tell us if you know" costs nothing; "go and find out" makes every
    review an open-ended search and reintroduces on the human side what Issue
    #722 rules out on the machine side."""
    sources_body = variant_body(VARIANT_HEADINGS[0])
    assert "not being asked to go looking" in sources_body, (
        "The prompts no longer state that the reviewer is not expected to "
        "research. Without that sentence they read as an instruction to go and "
        "look, which is the cost this wording exists to avoid."
    )


def test_the_knowledge_item_says_where_to_put_a_url():
    """The item asks for a URL; it has to say where it goes (Issue #736).

    Before this, "note it" named no destination. The only place a reader can
    write on an Issue is a comment, and the shared "How to Proceed" section in
    the same body says in bold that commenting is not enough and routes
    comments to `/wikicommit-fix` — which cannot register a source at all. The
    item asked for something the rest of the body then sent to the wrong tool.
    """
    sources_body = variant_body(VARIANT_HEADINGS[0])
    assert "put the URL in the comment" in sources_body, (
        "The knowledge prompt asks for a URL without saying where to "
        "put it, so the reader is left with the general rule that comments do "
        "not carry through."
    )
    assert "/wikicommit-generate <url>" in sources_body, (
        "The knowledge prompt no longer names the Skill that registers "
        "the URL, so a reviewer with write access is not told what to run."
    )


def test_the_knowledge_item_covers_a_reader_without_write_access():
    """The checklist was written for an operator who can run commands and the
    shared section for a reader who cannot (Issue #665). The URL route has to
    work for both, or the reader Issue #665 named is asked for something they
    have no way to deliver."""
    sources_body = variant_body(VARIANT_HEADINGS[0])
    assert "write access" in sources_body, (
        "The knowledge prompt no longer distinguishes a reviewer who "
        "can register the source from one who can only leave the URL for "
        "someone else."
    )


def test_how_to_proceed_exempts_a_url_from_the_wikicommit_fix_route():
    """The two paragraphs only work as a pair.

    Without this exception the same Issue body tells the reader to comment a
    URL in one place and, in bold, that comments go to `/wikicommit-fix` in
    another — and `/wikicommit-fix` reads a page's existing `sources` and never
    calls `add_source.py`, so the URL goes nowhere.

    Scoped to the shared section, not the whole file, for the reason
    `variant_body` gives: Step 9's generation-failure template carries a second
    `## How to Proceed` block, so a whole-file match would stay green with the
    exception moved out of the review Issue entirely.
    """
    shared = variant_body(SHARED_HOW_TO_PROCEED_HEADING)
    assert "are the exception" in shared, (
        "The shared \"How to Proceed\" section no longer exempts a URL from the "
        "/wikicommit-fix route, so the prompt and this section "
        "contradict each other again."
    )
    assert "cannot touch sources at all" in shared, (
        "The shared section no longer says why these need a different route. "
        "Without the reason, the next editor reading the single-track "
        "\"comments go to /wikicommit-fix\" rule removes the exceptions."
    )


def test_the_shared_url_exception_does_not_promise_this_page(variants):
    """The shared section goes into all three variants verbatim, so this
    sentence must not depend on page provenance.

    `/wikicommit-generate` pins `lang` to `primary_lang` and resolves
    `existing_path` only under `.wikicommit/entity/<primary_lang>/`, so it
    cannot update a translation, and it never writes to `.wikicommit/view/` at
    all. "Folds it into this page" is therefore false on two of the three
    variants — the two whose own checklists already say the opposite, that a
    fix belongs on the original or the grounding page (Issue #525 / #529).
    """
    shared = variant_body(SHARED_HOW_TO_PROCEED_HEADING)
    assert "into the page written from it" in shared, (
        "The shared URL exception claims a registered document lands on the "
        "page this Issue tracks. On a translation or a synthesized page it "
        "lands on the page that one derives from, so the reviewer closes a "
        "page nothing changed."
    )
    assert "leave this Issue open until" in shared, (
        "The shared URL exception no longer tells a reviewer who only comments "
        "the URL to keep the Issue open. Closing it flips review_status to "
        "reviewed and merges the page with the source still unregistered — the "
        "outcome the paragraph directly above it exists to prevent."
    )
    # The exception is shared text; it must reach every variant's body.
    for heading, body in variants.items():
        assert "the shared \"How to Proceed\" section above" in body, (
            f"The {heading!r} variant no longer inserts the shared section, so "
            "the URL exception never reaches its Issue body."
        )


def test_the_url_route_is_mirrored_in_the_design_doc():
    """`docs/DesignDoc-pipeline.md` carries the Japanese mirror of both
    templates. A route that exists in only one of the two is the drift these
    mirrored templates keep producing."""
    pipeline = (
        Path(__file__).parent.parent / "docs" / "DesignDoc-pipeline.md"
    ).read_text(encoding="utf-8")
    assert "コメントに URL を書いてください" in pipeline, (
        "The Japanese mirror of the checklist no longer tells the reader where "
        "to put a URL."
    )
    assert "`/wikicommit-fix` はソースに一切触れられないためです" in pipeline, (
        "The Japanese mirror of the shared section no longer carries the "
        "exceptions, or no longer says why they need a different route."
    )
    assert "それを元に書かれたページへ統合され" in pipeline, (
        "The Japanese mirror of the shared section claims the document lands "
        "on the page this Issue tracks, which is false on the translation and "
        "synthesized variants it is also inserted into."
    )
    assert "この Issue は Close しないでください" in pipeline, (
        "The Japanese mirror of the shared section no longer tells a reviewer "
        "who only comments the URL to keep the Issue open."
    )


def test_every_variant_asks_for_one_line_on_what_landed(variants):
    """The product `review_status` can actually carry (Issue #740).

    A two-valued field holds an event, not a claim, and the event is that this
    page's knowledge reached a person. The line is that event's trace. Drop it
    and the Issue is back to being a box to tick, which is the shape that made
    closing a signature in the first place.
    """
    for heading, body in variants.items():
        assert LINE_ASK_PHRASE in body, (
            f"The {heading!r} template no longer asks for a line on what the "
            "reader took away, so closing records nothing but the click."
        )


def test_every_variant_says_this_is_not_a_test(variants):
    """Without it the request for a line reads as something the reader will be
    marked on, and the weight Issue #740 removes comes back in another form.

    It is also true in a way that matters: there is no correct answer, so there
    is nothing to mark, so there is nothing to fake — which is exactly why a
    line can be asked for at all where a quiz could not.
    """
    for heading, body in variants.items():
        assert NOT_A_TEST_PHRASE in body, (
            f"The {heading!r} template no longer says the line is not a test of "
            "understanding, so it reads as an examination."
        )


def test_every_variant_states_the_check_the_machine_already_ran(variants):
    """What replaced the removed source-fidelity items.

    Issue #723 removed those items because Pass 4 already does that work; Issue
    #740 removed the checkbox around the rest. Between them, a reader given only
    the prompts would conclude nothing checked this page at all — the reverse
    error, and the one Issue #740 itself warns against making twice. Issue #751
    put the machine's verdict on the published page, which is what lets the
    prompts be introduced as the part that check does *not* cover.
    """
    for heading, body in variants.items():
        assert MACHINE_HALF_PHRASE in body, (
            f"The {heading!r} template no longer states that the page was "
            "already checked against what it was written from, so the prompts "
            "below it read as the only checking that happens."
        )


def test_no_variant_says_this_is_not_a_review(variants):
    """All three products come from one reading and the word covers the whole of
    it (Issue #740, following Issue #583's line on `ingest`). Saying otherwise
    would also invite renaming the label, the workflow and the Skill — and
    renaming the `wikicommit-review` label re-opens every tracking Issue as a
    duplicate."""
    for heading, body in variants.items():
        assert "not a review" not in body.lower(), (
            f"The {heading!r} template claims this is not a review. What changed "
            "is which product gets recorded, not what the reading was."
        )


def test_review_skill_asks_the_human_only_items_of_the_reviewer():
    """`wikicommit-review` Step 4 cannot answer either human-only item — the
    knowledge one is ruled out by the evidence-binding discipline that makes
    the rest of the step trustworthy. It reports machine findings and puts
    these two to the person."""
    assert "human-only prompts" in REVIEW_SKILL, (
        "wikicommit-review/SKILL.md no longer routes the human-only "
        "prompts to the reviewer's confirmation prompt."
    )
    assert "not** being asked to go looking" in REVIEW_SKILL
    assert "a real person or organization" in REVIEW_SKILL


def test_review_skill_no_longer_claims_the_same_checklist_as_the_template():
    """Step 4 used to declare it applied "the same review perspective the
    tracking-Issue template asks human reviewers to apply". That is now false
    in both directions and would send an LLM at questions it must not answer."""
    assert "the same review perspective the tracking-Issue template" not in REVIEW_SKILL


# --- The conditional type-selection item (Issue #729) -----------------------
#
# This item lived in the design doc and in `wikicommit-review` but not in the
# template that actually writes the Issue, and nothing noticed — the same class
# of silent drift the tests above exist to stop, which is why the guard belongs
# here rather than in a file of its own.

TYPE_ITEM_PHRASE = "the right type for this subject"
PASS_2B_PROVENANCE = ("`generate-interactive`", "`generate-auto`")


def test_only_the_sources_variant_carries_the_type_selection_item(variants):
    """The type decision belongs to the page the type was chosen for. A
    translation inherits it, and a synthesized page has no source-driven type
    choice to second-guess — the same three-way split (Issue #525) that keeps
    the reviewer-knowledge item out of those two variants."""
    assert TYPE_ITEM_PHRASE in variants[VARIANT_HEADINGS[0]], (
        "The `sources` checklist no longer asks whether the type fits. This is "
        "the only place a tracking Issue surfaces a type Pass 2b may have added "
        "with no human confirmation at all (Issue #507)."
    )
    for heading in VARIANT_HEADINGS[1:]:
        assert TYPE_ITEM_PHRASE not in variants[heading], (
            f"The {heading!r} checklist now asks about type selection, but that "
            "decision was not made for this page."
        )


def test_the_type_item_stays_conditional_and_is_never_commented_out(variants):
    """Emitted unconditionally it becomes a fifth standing item and pushes the
    checklist past the cap that keeps it read; emitted as an HTML comment it
    travels into the Issue body verbatim, the way the `wikicommit-page` marker
    does."""
    body = variants[VARIANT_HEADINGS[0]]
    assert "conditional: emit it only when" in body
    assert "drop the whole line otherwise" in body
    assert "Do not emit it commented out" in body


def test_the_type_item_says_no_automation_judged_the_choice(variants):
    """The preamble splits the list into "unmarked = a second look at what the
    machine already did" and "marked = no automation covers it". This item is
    unmarked but nothing automated judges whether a type *fits*: Pass 4 checks
    claims against sources, and `check_schema_org_type.py` only confirms the
    type exists in the vocabulary. Without this sentence the reader skims the
    one item that has had no confirmation of any kind."""
    body = variants[VARIANT_HEADINGS[0]]
    assert "no automated check judges whether it" in body


def test_no_checklist_names_the_removed_recommended_field():
    """Issue #495 removed the type-level `recommended` list; `properties:` took
    over its role. A reviewer sent to look at a `recommended` field opens the
    schema file and finds nothing by that name."""
    for name, text in (("wikicommit-merge", MERGE_SKILL), ("wikicommit-review", REVIEW_SKILL)):
        assert "`recommended`-field selection" not in text, (
            f"{name}/SKILL.md asks about a `recommended` field that schema files "
            "have not had since Issue #495."
        )


def test_both_skills_resolve_the_condition_the_same_way():
    """`wikicommit-merge` decides whether to emit the item and
    `wikicommit-review` decides whether to check it; if the two conditions
    drift, the same page gets reviewed against two different checklists
    depending on which entry point was used."""
    for name, text in (("wikicommit-merge", MERGE_SKILL), ("wikicommit-review", REVIEW_SKILL)):
        assert "wikicommit.provenance" in text, (
            f"{name}/SKILL.md no longer resolves the type item's condition via "
            "the schema file's permanent `provenance` stamp."
        )
        for value in PASS_2B_PROVENANCE:
            assert value in text, (
                f"{name}/SKILL.md no longer names {value} as a Pass 2b provenance."
            )


# --- Reporting that a source itself is wrong (Issue #743) -------------------
#
# Nothing in the template used to question whether a source is any good. Every
# item measured the page *against* its sources, so a page faithfully repeating
# a source's error passed all of them — and the gap is structural rather than
# an oversight: Pass 4's evidence-binding rule (Issue #442) makes the sources
# the standard, and under that discipline the machine cannot doubt them. Issue
# #737 built the receiving end (`status: retracted` plus a hand-written
# `## Retraction Reason`), which is what makes asking worth anything.

SOURCE_VALIDITY_PHRASE = "wrong with a source"


def test_only_the_sources_variant_asks_about_the_sources_themselves(variants):
    """A translation has no `sources` of its own — it inherits the original's —
    and a synthesized page has `derived_from` instead, so on both the documents
    in question belong to a different page. Same split Issue #525 created the
    three variants for and Issue #529 made `wikicommit-fix` follow; asking on
    all three would invite retracting a source on the strength of a page one or
    two removes from it."""
    assert SOURCE_VALIDITY_PHRASE in variants[VARIANT_HEADINGS[0]], (
        "The `sources` template no longer asks whether a source itself is "
        "sound. No automated layer can reach that judgment: every check "
        "measures the page against its sources."
    )
    for heading in VARIANT_HEADINGS[1:]:
        assert SOURCE_VALIDITY_PHRASE not in variants[heading], (
            f"The {heading!r} template now asks about its own sources, but it "
            "has none — the documents belong to the page it derives from."
        )


def test_the_other_two_variants_redirect_a_source_problem(variants):
    """Dropping the prompt is only half of it. Without a redirect, a reviewer
    who does spot a bad source on a translation or a synthesized page is left
    with nowhere to put it — the same reason those variants already redirect a
    wrong fact rather than staying silent about one."""
    for heading in VARIANT_HEADINGS[1:]:
        assert "The same goes for a source" in variants[heading], (
            f"The {heading!r} template drops the source prompt without saying "
            "where a source problem belongs, so the reviewer has no route."
        )


def test_the_source_prompt_says_the_page_check_does_not_cover_it(variants):
    """The one sentence that makes this a separate question rather than a
    restatement of the ones above it. A reviewer who has just confirmed the
    page matches its sources has, on the face of it, no reason left to look at
    the sources — and that is exactly the case this prompt exists for."""
    body = variants[VARIANT_HEADINGS[0]]
    assert "measures the page *against* its sources" in body, (
        "The source prompt no longer explains why passing every automated "
        "check says nothing about the sources, so it reads as a repeat of the "
        "items above it and gets skipped."
    )


def test_the_source_prompt_reaches_the_retraction_route():
    """Issue #737 built the receiving end and it is written by hand, so the
    prompt has to name it. Without that, a report lands in a comment the shared
    section otherwise says does not carry through."""
    shared = variant_body(SHARED_HOW_TO_PROCEED_HEADING)
    assert "status: retracted" in shared, (
        "The shared section no longer names the retraction that receives a "
        "report about a source, so the report has no destination."
    )
    assert "/wikicommit-status" in shared, (
        "The shared section no longer says that retracting a source surfaces "
        "the pages standing on it, so retracting looks like the end of it."
    )


def test_the_source_route_is_mirrored_in_the_design_doc():
    """Both templates exist twice, and a route present in only one of the two
    is the drift these mirrored templates keep producing."""
    pipeline = (
        Path(__file__).parent.parent / "docs" / "DesignDoc-pipeline.md"
    ).read_text(encoding="utf-8")
    assert "ソース自体がおかしいと思った点" in pipeline, (
        "The Japanese mirror of the `sources` template no longer asks about "
        "the sources themselves."
    )
    assert "`status: retracted` と理由を書き" in pipeline, (
        "The Japanese mirror of the shared section no longer names the "
        "retraction route a source report goes to."
    )
    assert "ソースについても同じで" in pipeline, (
        "The Japanese mirror no longer redirects a source problem on the "
        "translation and synthesized variants."
    )


def test_review_skill_asks_about_the_sources_themselves():
    """`wikicommit-review` reaches the same reviewer by another door, and Issue
    #729 established that the two entry points must not ask different things."""
    assert "wrong with a **source**" in REVIEW_SKILL, (
        "wikicommit-review/SKILL.md no longer puts the source-validity "
        "question to the reviewer, so the same page gets asked different "
        "things depending on which entry point was used."
    )
    assert "status: retracted" in REVIEW_SKILL, (
        "wikicommit-review/SKILL.md no longer routes a source report to the "
        "retraction that receives it."
    )


# ── Issue #800: what closing states, and what a reader does when something
#    stands out ────────────────────────────────────────────────────────────────

CLOSING_STATES_PHRASE = "Closing this Issue states two things"
COMMENT_AND_LEAVE_OPEN_PHRASE = "a comment is all that is asked of you"
NOT_GOING_LOOKING_PHRASE = "not being asked to go looking"


def test_every_variant_says_closing_states_two_things(variants):
    """Issue #800 raised the second half from implication to claim.

    Issue #740 narrowed `reviewed` to an event and, in doing so, left the
    templates saying only what closing does *not* mean ("not that the page is
    correct"). A reader could then draw nothing at all from the fact that a
    person read a page and said nothing — which is the opposite of what the
    trust ladder is for. The claim that was added back is about the *reading*
    ("nothing struck you as obviously wrong"), not about the page, which is why
    it still fits a two-valued field.
    """
    for heading, body in variants.items():
        assert CLOSING_STATES_PHRASE in body, (
            f"The {heading!r} template no longer says closing states two "
            "things, so the reader is told only what closing does not mean."
        )
        assert "obviously wrong" in body, (
            f"The {heading!r} template no longer names the second half of what "
            "closing states."
        )


def test_every_variant_tells_a_reader_to_comment_without_closing(variants):
    """The reader is not the one who has to fix it (Issue #800).

    Before this the templates said to fix the page first and then close, which
    asks work of a reader who, by Issue #665's own finding, may not even have
    the access to do it. This route lives in prose and nothing else would notice
    if it were dropped — the same reason Issue #736 put a test on its own
    two-part route.
    """
    for heading, body in variants.items():
        assert COMMENT_AND_LEAVE_OPEN_PHRASE in body, (
            f"The {heading!r} template no longer tells a reader who noticed "
            "something that a comment is enough."
        )
        assert "do not close" in body.lower(), (
            f"The {heading!r} template no longer tells that reader to leave the "
            "Issue open, so a comment plus a close would merge the page as "
            "reviewed with the problem unaddressed."
        )


def test_the_second_half_never_becomes_an_instruction_to_go_looking(variants):
    """The one sentence keeping "obviously wrong" from turning into a search.

    Issue #800's whole basis for putting a claim back into a two-valued field is
    that it ends when the reading ends. Drop this and "did anything strike you"
    slides into "did you look hard enough", which is a negative proof and
    exactly the weight Issue #740 removed.
    """
    for heading, body in variants.items():
        assert NOT_GOING_LOOKING_PHRASE in body, (
            f"The {heading!r} template no longer says the reader is not being "
            "asked to go looking, so the claim it now carries reads as a search."
        )


def test_the_how_to_proceed_section_does_not_ask_the_reader_to_fix_it():
    """The shared section, checked once — it is inserted verbatim into all three."""
    section = variant_body(SHARED_HOW_TO_PROCEED_HEADING)
    assert "You do not have to make the fix yourself" in section, (
        'The shared "How to Proceed" section no longer relieves the reader of '
        "making the fix (Issue #800)."
    )
    assert "edit the page first" not in section, (
        'The shared "How to Proceed" section is back to telling the reader to '
        "edit the page before closing, which asks work of someone who may not "
        "have write access at all (Issue #665)."
    )


def test_the_two_claims_are_mirrored_in_the_design_doc():
    """Issue #729's three-way agreement, for the wording Issue #800 changed.

    The Japanese design record in DesignDoc-pipeline.md §6.2 is the other copy
    of these templates; when the two drifted before, the design doc described a
    checklist the Skill no longer wrote.
    """
    design_doc = (
        Path(__file__).parent.parent / "docs" / "DesignDoc-pipeline.md"
    ).read_text(encoding="utf-8")
    assert design_doc.count("Close が述べるのは 2 つです") == 3, (
        "DesignDoc-pipeline.md §6.2's three variants no longer all say that "
        "closing states two things (Issue #800 / #729)."
    )
    assert design_doc.count("引っかかる点があった場合は") == 3, (
        "DesignDoc-pipeline.md §6.2's three variants no longer all tell a "
        "reader who noticed something to comment without closing."
    )
    assert "修正が必要な場合は先にページを修正" not in design_doc, (
        "DesignDoc-pipeline.md still tells the reader to fix the page before "
        "closing (Issue #800)."
    )


def test_the_review_skill_states_the_same_two_claims():
    """Route B records `reviewed` directly, so it has to mean the same thing.

    `wikicommit-review` writes the field itself instead of closing an Issue. If
    only the tracking-Issue templates carried the second claim, the same field
    would mean two different things depending on which route set it.
    """
    assert "Recording `reviewed` states two things" in REVIEW_SKILL, (
        "wikicommit-review no longer states what recording `reviewed` claims, "
        "so route B and route A disagree about the same field (Issue #800)."
    )
    assert "Do not record `reviewed` over a flagged problem" in REVIEW_SKILL, (
        "wikicommit-review no longer refuses to record a review over a problem "
        "the reviewer just raised, which would state something they contradicted."
    )
