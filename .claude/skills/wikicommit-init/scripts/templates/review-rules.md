---
rules_version: 1
wikicommit:
  # Machine-readable header only. The rules themselves are the prose below.
  # `rules_version` is bumped whenever any rule in this file changes; a review
  # subagent must echo it back so the orchestrator can tell a review that read
  # these rules from one that did not (Issue #752).
  applies_to:
    - generate-pass4
    - review-skill
    - synthesize-step5.5
---

# WikiCommit review rules

The one place the review discipline is written. Every review path reads this
file; none of them restates it (Issue #752).

Before this file existed the same rules lived in three Skills at once, and the
three had already drifted apart — some checks existed in only one of them, and
nobody had decided which version was right. Deciding that is what this file is.

**Do not copy these rules back into a SKILL.md.** What belongs there is the
*choreography* — how a subagent is launched, what happens on FAIL, retries,
where the page is written, how a status is updated. What belongs here is *what
to inspect*. A test enforces the split.

---

## Part 0 — Reading this file

You have been handed a page and some evidence, and asked to decide whether the
page is supported by that evidence.

### Only what is marked `SOURCE` is evidence

Your prompt may contain material beyond the evidence — a summary of a source,
an analysis JSON describing what the generator decided to write, a note about
why a passage was phrased a certain way, or the findings of a previous review
round. **None of that is evidence.** Judge only against blocks the prompt marks
as `SOURCE`.

This matters because the prompt is usually assembled by the very agent that
wrote the page. A summary is *that agent's reading* of a source, and checking a
page against a summary is not checking it against the source; the check would
pass precisely when the generator's misreading was consistent. A previous
round's findings would anchor this round to the last one. If any of that
appears in your prompt anyway, treat it as background and do not let it decide
anything.

### Echo `rules_version` in your answer

The JSON you return must carry the `rules_version` from this file's
frontmatter. That is how the orchestrator can tell a review that read these
rules from one that skipped them — without it, a review that never opened this
file degrades to "compare the page to the source" and **its output still looks
completely normal**.

---

## Part 1 — Rules that hold on every path

### 1. Evidence binding

Every check below is a *source-to-claim* check, not a *fact* check. Decide
PASS/FAIL solely on whether the literal text of the evidence in front of you
states the claim — **never** on your own pretrained or world knowledge of
whether the claim happens to be true.

A claim that is well known to be true (a famous person, a widely reported
event, a well-known technical fact) must still **FAIL** if the evidence does
not actually contain it. That matters most when the "evidence" is itself
boilerplate — a JS-rendered page's login or navigation shell with no article
body — that happens to concern a well-known topic. Conversely, an obscure or
surprising claim passes if the evidence does state it.

Do not fill gaps in the evidence from your training data.

### 2. Completeness is not a criterion

Something the evidence states that the page does *not* say is, on its own, not
a defect. What a page records and what it leaves out is decided elsewhere — by
the type template's `granularity` rules and by the generation step's
abstraction rules — and this review does not re-open that judgment. "The
evidence covers more than this" is never a finding.

This exemption is deliberately one-sided. It exempts the **shortfall** side
only and narrows none of the FAIL conditions below. Do not restate it as "only
claims absent from the evidence can FAIL": several defects this review exists
to catch are claims that *are* in the evidence — an attribution swap (check 5),
an unattributed single-source formulation (check 6), and a page following the
weaker of two disagreeing sources (check 7) all quote something the evidence
actually says.

### 3. Do not research outside what you were given

Rule 1 says what may count as evidence; this says what to do when it runs out.
When the evidence is too thin to settle a claim either way, do not run a web
search, fetch a URL, or open any document that was not handed to you. Settle it
on the text in front of you — which under rule 1 means an unsupported claim is
a FAIL.

One exception: evidence whose own wording is internally inconsistent or garbled
such that the review cannot proceed without checking it. Say so explicitly in
that entry's `instruction` when you take it.

Assembling the review's own inputs is not research and is not what this rule
stops. Neither is re-fetching a source the page already declares.

### 4. What to return

The agent-to-agent JSON: `result: "PASS" | "FAIL"`, an `issues` array, and
`rules_version`.

Each `issues` entry carries `type` (one of `HALLUCINATION` / `CONTRADICTION` /
`MISSING_SOURCE`), `claim`, `source_file`, `source_lines`, `source_quote`,
`instruction`, and `page_at_fault` on cross-page entries only.

`source_file` is what tells a page conflict from a source one: a path under
`.wikicommit/entity/` or `.wikicommit/view/` means the conflict is with a page,
anything else means a source document.

---

## Part 2 — The checks

Each check names the paths it applies to. A check that does not name your path
is not yours to run. **Your path is stated in your prompt** — one of
`generate-pass4`, `review-skill` or `synthesize-step5.5`, the same three names
this file's `applies_to` lists. If your prompt does not state one, say so and
stop rather than guessing: guessing wrong silently drops the checks that path
depends on, and the output still looks normal.

### 1. Claim support — all paths

Verify that the page's key claims are supported by the evidence (hallucination
detection).

If the page's frontmatter has an `expires_at` value, treat it as a claim like
any other: the evidence must state that exact date (or, where several deadlines
are stated, the earliest of them) for an entity this page covers. An
`expires_at` invented or misread fails review the same way a fabricated
body-text claim would.

### 2. Granular fact verification — all paths

"Key claims" includes individually-checkable concrete details embedded in body
prose — a stated date, a specific publication or article title, a version
number, a named event — not only the page's overall thesis.

A claim that is broadly correct but wrong in one such checkable detail must
still **FAIL** (`type: HALLUCINATION`). Approximate correctness on the broad
claim does not excuse an inexact specific detail: if the general fact that a
named person wrote about a topic is true, but the date given for that
publication is not the date the evidence states, that is a FAIL.

### 3. Naming vs. inventing — all paths

When the evidence describes one party giving a name or label to an existing or
emerging practice ("X calls this Y", "X coined the term Y"), a page that
instead states X *invented*, *created*, or *originated* the underlying practice
is a **FAIL** (`type: CONTRADICTION`) — even though both claims share the same
surface subject.

Naming a practice and originating it are different, independently verifiable
facts, and the evidence stating one does not license inferring the other.

This is a separate check from check 5: that one catches wording attributed to
the wrong *party*, this one catches the wrong *kind of act* attributed to the
correct party.

### 4. Cited documents the page does not hold — `generate-pass4`, `review-skill`

When a body claim cites, names, or clearly implies a specific document (an
article title, a specific publication event) that is not among the evidence
assembled for this review, that is a **FAIL** (`type: MISSING_SOURCE`) even if
the surrounding narrative sounds plausible. Do not accept "this is the kind of
thing this source would say" as a substitute for the cited document actually
being present.

**Apply this to secondary citations too.** It holds even when the specific
date or title was not asserted outright by the page but only paraphrased from a
source's own passing mention of a *different* document. The test is not "does
some evidence in front of me say this" but "is the specifically dated or titled
document the page names actually among the evidence assembled for this review".
A source merely mentioning another document is not the same as that other
document having been ingested. This is exactly the loophole that let a secondary
citation slip past in practice.

Read that as the assembled evidence, never as the page's own `sources` field.
A translation carries no `sources` of its own and inherits its parent's, so
matching against the field would flag every document it names — starting with
the one it was translated from.

**On `synthesize-step5.5` this check does not apply**, and `MISSING_SOURCE`
means something different there — see Part 3. **It does not apply to a page
carrying `derived_from` on `review-skill` either**, for the same reason: the
evidence there is grounding pages, so a claim they do not carry means no page
states it, not that the wiki is missing a document — there would be no URL to
recommend registering.

### 5. Attribution correctness — all paths

Truth-checking alone cannot catch an attribution swap, because a misattributed
claim can still be true according to *some* source — just not the one the page
names.

For every claim the page presents as belonging to a specific named origin (a
direct quote, or a claim phrased as "X says / argues / proposes…"), verify that
the *specific* cited origin actually states it — not merely that some evidence
does. If the evidence shows the wording came from a different party than the
one the page names, that is a **FAIL** (`type: CONTRADICTION`) even though the
claim's content is accurate: the attribution itself is the defect. Say in
`instruction` which party the wording actually belongs to.

### 6. Unattributed single-source formulations — all paths

Check whether the page states a definition, framework, or formulation as
unqualified general fact when the evidence shows it is actually one specific
party's own proposal (a single paper, blog post, or vendor's argument) rather
than an established or widely agreed term.

If so, **FAIL** (`type: CONTRADICTION`). The fix is not to remove the content
but to add attribution phrasing, so say that in `instruction` — a retry can
then produce a properly attributed version rather than a factually identical
but still misleading one.

### 7. Source-vs-source disagreement — `generate-pass4`, `review-skill`

When the page has two or more sources, checking each claim against *some*
source is not enough. Sources can disagree with each other, and taking whichever
one happens to be at hand launders an error into the wiki.

Where two sources state the same fact differently, prefer the one that **treats
that fact's subject as its own subject** over one that mentions it in passing:
a list, index, directory, or roster entry is weaker evidence about an item than
a document about that item.

Set `source_file` / `source_quote` to the source that should have been followed
— the stronger one, not the one the wrong wording was found in — say which
source the page followed and why in `instruction`, and **FAIL**
(`type: CONTRADICTION`) if the page took the weaker one.

In one pilot a ward page said a football club was headquartered in that ward.
The only thing that said so was a one-line bullet in a city-wide company list
in a *different* source, contradicted by the club's own article and by the same
page's other sources — and the surrounding bullets in that list were all
correct, so nothing looked wrong. This is your job even though both sources are
already in front of you: reading them one at a time against the page never
surfaces that they disagree.

### 8. Cross-page contradiction, one hop out — `generate-pass4`

A page can be perfectly faithful to its own sources and still contradict
another page in the same wiki. One pilot published 1727 and 1728 as the year of
one land reclamation, on two pages that each quoted their own source correctly.

You will be given, as additional context, the existing pages one WikiLink hop
away from the page under review. Ask only whether the same fact is stated
differently — not for a general review of those pages.

**Those pages are context for that comparison only — never evidence.** A claim
none of this page's own sources state is still a FAIL even when a hop-out page
repeats it: those pages are LLM-generated too, and accepting one as support
would launder a hallucination from page to page (rule 1).

Route what comes back by which page is wrong. Both fields must be set:

- The **page under review** is wrong (its own sources support the other page's
  version, or it went beyond what its sources say) → `page_at_fault:
  "under-review"`, and **FAIL** like any other finding.
- The **other page** looks wrong (this page's sources do support what it says)
  → `page_at_fault: "other"`, and **not a FAIL**. An entry like this never on
  its own makes `result` `"FAIL"`; when it is the only kind of defect found,
  return `result: "PASS"` and still list it in `issues`.

  Failing it instead would regenerate a page that is already right, surface the
  identical unfixable finding on every attempt, and end with a correct page
  discarded. This direction matters: in the pilot case above it was the
  *existing* coarse page that was wrong, not the new one.

### 9. Boundary breach — `synthesize-step5.5`

You will be given the page's declared `kind` and the one Boundary line for it.
Report a breach as an `issues` entry with `type: "CONTRADICTION"`, an empty
`source_file` (nothing in the grounding contradicts it — the page contradicts
its own declared kind) and an `instruction` saying what to remove or rewrite.
A breach makes `result` `"FAIL"`.

Without this check the kind is a label nobody reads, and it drifts. The four
that go wrong quietly: a `landscape` that states counts, a `pattern` with no
case count and no pages named, a `comparison` that ranks, a `practice` that
tells the reader what to do.

---

## Part 3 — Differences by path

### `generate-pass4` — a page against the documents it was written from

Evidence is the extracted text of the page's own sources. All checks apply.

**This review is never independent of the generation it checks** — it runs in
the session that just wrote the page. That is why rule 1 and Part 0's `SOURCE`
rule carry the weight here: they are the only thing separating the check from
the writing.

### `review-skill` — a second look, later and possibly by another model

Evidence is the page's sources, re-fetched. For a translation with no `sources`
of its own, that is the parent page's sources; for a page with `derived_from`,
the grounding pages.

Check 8 does not apply: there is no subagent to hand the extra pages to, no
retry loop for a finding to feed, and gathering them costs the reviewer time
they did not ask for.

**Report findings; do not decide.** This path returns observations to a human
rather than a PASS/FAIL that gates a write.

**Independence is worth stating here and only here.** If the model running this
review is the same as the page's `generated_by` / `translated_by`, say so and
recommend re-running in a separate session or under a different model. On
`generate-pass4` that note would fire every single time and say nothing.

**What to check depends on how the page was made:**

- **`translated_from`** — does the translation reflect the meaning of the
  source page? Is terminology consistent with the `DefinedTerm/` glossary? Does
  it read naturally rather than as an awkward literal rendering?
- **`derived_from`** — does the content reflect the pages listed there? Any
  claim they do not support? Are the WikiLink targets right?
- **otherwise** — does the content match the source documents? Factual errors
  or hallucinations? Are the WikiLink targets right?

**Two questions on this path belong to a human, not to you.** Whether the page
conflicts with what the reviewer already knows is ruled out by rule 1 — an LLM
answering it would be breaking the discipline that makes everything else here
trustworthy. Whether a sentence unfairly harms a real person or organization is
a contextual judgment whose false positives delete legitimate writing. Report
machine findings only and leave those two to be asked of the reviewer directly.

### `synthesize-step5.5` — a page against other pages in this wiki

Evidence is the grounding page bodies. `source_file` therefore holds a page
path on every entry, which is consistent with rule 4 rather than an exception
to it: every piece of evidence this review has *is* a page.

**`MISSING_SOURCE` means something different here.** It means *no grounding
page states this at all* — not that a cited document is missing. There is
therefore no page to name: leave `source_file` empty on those entries rather
than naming the nearest one. This is why check 4 does not apply here, and why
a finding here is not a document worth registering.

`MISSING_SOURCE` matters more on this path than anywhere else: nothing else in
WikiCommit looks at whether a synthesized claim has any backing at all.

**Do not read the grounding pages' own sources.** They are one step further out
than this review reaches. An unsupported claim is a `MISSING_SOURCE` FAIL,
which is the correct outcome; going to look for support instead would launder
it into a pass.

**Synthesis is not transcription.** A claim does not have to appear verbatim —
drawing a stated connection between two grounding pages is the point of the
exercise. The line is whether the claim's *content* is carried by the grounding
text: a comparison, ordering, or grouping of facts each grounding page states
is supported; a new fact none of them states (a date, a name, a quantity, a
causal claim) is not.

**Grounding pages that disagree with each other are reported, not failed** —
`page_at_fault: "other"`, exactly as in check 8, and for the same reason: this
path cannot edit a grounding page, so failing would produce a correct synthesis
that draws the identical unfixable finding on every retry until it is
discarded.

**Both pages have to be named inside the one entry.** An entry carries a single
`source_file` and a single `source_quote`. On `generate-pass4` that is enough
because the second page is implicitly the page under review; here the page under
review is the synthesized page and *neither* side of the disagreement is it.
Put one grounding page in `source_file` with its wording in `source_quote`, and
name the counterpart page — its path and its version of the same fact — in
`claim`. Otherwise only half the pair can be reported, and half a pair is not
actionable.
