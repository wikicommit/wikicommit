---
pass_token: "daf82d23"
---

# Step 0: Survey Mode (`survey`)

The workflow engine hands you this step only when the run was started without a `<topic>`. Report one outcome when it is done:

- `chosen` — the person chose an angle (or typed a topic of their own). Pass the topic, the kind proposed with it when there is one, and the grounding cap when the person named one with their choice. Pass the topic through a quote-delimited heredoc — it is free-form text, and a plain `"<topic>"` embedding would let shell metacharacters in it be evaluated:

  ```bash
  python .wikicommit/scripts/skill_workflow.py done <run> --step survey --outcome chosen \
      --token daf82d23 --add "topic=$(cat <<'EOF'
  <the chosen topic>
  EOF
  )" [--add kind=<kind>] [--add max_grounding=<N>]
  ```

- `none` — nothing was chosen, no answer arrived, or nobody can answer in this run. The workflow engine closes the run as finished (`--token daf82d23`, no `--add`); then say the wiki was left untouched.

Every later step starts by turning `<topic>` into a search query, so with a
`<topic>` argument the Skill can only write about something the person already
knew to ask for. The angles worth writing about are often the ones that only
appear once you look at several pages at once — a period shared by several
`Event` pages, several `Place` pages that turn out to connect through one
`Person`, a subject whose treatment is split across two type directories.

**This step's output is not deterministic.** The same wiki will suggest
different angles on different runs. That is expected: this is idea support, not
a quality gate, and it is why nothing here writes to disk until you have chosen.

## 0.1 Build the reduced view

```bash
python .wikicommit/scripts/build_survey_view.py
```

The wiki's full text does not fit in one context, so the script reduces every
page to the lines that carry its cross-cutting structure — title, type, tags,
`properties.description`, its `##` section headings, and the WikiLinks it makes
— and adds the rankings computed from the link graph (`HUB:`, `TAG:`, `TYPE:`).
It lists the wiki's `primary_lang` by default; pass `--lang all` to include
translations, though they restate the same content in another language and
mostly cost context. The link graph is always built from every language.

Read the whole output into context. If it prints a `TRUNCATED:` line, say so
plainly — the survey is incomplete, and the angles it proposes come from only
the most-linked part of the wiki. Offer to re-run with a higher `--max-pages`.

**What this view can and cannot see.** Section headings are the cheapest part of
a body that still names what it covers, and the link graph is where the strongest
cross-page patterns live — "several `Place` pages connect through one `Person`"
is not a statement about any page's text at all, and only a view holding all of
them at once can find it. What the view does not have is body prose: a pattern
that exists only in wording, with nothing in the headings, tags or links to hint
at it, will not surface here. Do not read every body through chunked subagents
to reach those: it reads the whole wiki on each run, and evidence for one
cross-page pattern split across two chunks is seen by neither subagent.

## 0.2 Propose angles

From that view, propose **at most 5** angles, matching the count at which the
other Skills stop and ask (`wikicommit-generate` / `wikicommit-collect` /
`wikicommit-translate` all use 5). Fewer is fine; a wiki with little structure
in it should get few. For each, give:

- a short topic phrase, in `primary_lang`, in the form the `ground` step can take as `<topic>`
- the **kind** it would be written as (the table in `references/write-page.md`), or none if no kind fits
- one line on what makes it worth writing, naming the specific pages that
  suggested it — and how many there are, so an angle that would exceed the
  grounding cap is visible before it is chosen. The pages named here are carried
  to the `ground` step as grounding candidates alongside whatever the search returns

**Work through the kinds to find them.** "Propose angles" on its own has no
structure, and the view's own output lines up with the kinds well enough to be
read that way — each row below says where in the view to look:

| Look at | Suggests |
|---|---|
| A `TYPE:` holding a handful of pages of one type | `comparison` — put them side by side and draw out the differences |
| A `TAG:` recurring across many pages | `pattern` — a shape repeating often enough to describe |
| A `HUB:` with many backlinks, or a type barely touched | `landscape` — the entry point into an area |
| Several `Event` pages, or pages whose headings carry dates | `timeline` |
| One `##` heading repeating across pages about one thing | `practice` (several accounts of the same thing) or `debate` (the same question answered differently) |

This is a way in, not a rule: an angle the view supports but no row above
predicted is still worth proposing. Propose only angles the view actually
supports — one no page in the list speaks to would send the search into a
query that returns nothing, and the synthesis, grounded solely in the pages
read, has no way to write it.

## 0.3 Let the person choose

Present the numbered list and ask which to write about. They can also type a
topic of their own, in which case use that verbatim. Add one line under the list
saying that a synthesized page is grounded in at most 30 pages by default (or
the `--max-grounding` value given), and that the person can name a different
number with their choice or re-run with `--max-grounding <N>`.

If the answer is not a choice — no answer arrives, or nothing appeals — report
`none`. Do not pick one on your own: this Skill writes primary wiki content, and
the whole point of this step is that the person, not the model, decides what the
wiki gets. If this Skill was invoked without anyone there to answer, `none` is
the correct outcome; re-run it with an explicit `<topic>` to skip the survey.
This is a run that finished, not one that died partway — which is why `none`
closes the run as finished rather than leaving it open.

Rejected angles are not recorded anywhere. The view is rebuilt from the wiki on
every run, so any angle still supported by the wiki can be proposed again;
writing down the ones that were passed over would only create the false promise
that they are queued for later (the same reasoning `wikicommit-generate` Pass 2b
applies to type candidates it declines).

The chosen phrase becomes `<topic>` (`--add topic=`), and the kind proposed
alongside it is carried to the `write` step as this page's `kind` (`--add kind=`;
the person may say a different one, or none — then leave it out). Nothing else
changes from here on: because `<topic>` reaches the search as ordinary free-form
text, it goes through the same quote-delimited heredocs every search term
already uses there.
