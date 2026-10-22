# Writing rules for every page

> **Paths in this file.** `references/…` is relative to the Skill's directory (the parent of this `references/` directory), not to the repository root — the Skills may be installed under `.claude/skills/` or `.agents/skills/`.

These are the rules for how a page's body is written, whichever Skill writes it and whichever form its template takes. Two Skills read this file:

| Who | Writes | Reads "the source" as |
|---|---|---|
| `/wikicommit-generate` Pass 3 (`references/pass3-generate.md`) | an entity page | the source documents the page is written from |
| `/wikicommit-synthesize` Step 5 (that Skill's own `write-page.md` reference file) | a view page | the grounding pages' body content |

`/wikicommit-synthesize` adds the rules only a view page needs, in its own Step 5. **Do not restate these rules in either Skill.** Kept in two places, one copy gets fixed and the other does not, and entity and view pages drift apart in how they read. A change to how every page is written goes here.

- **Lead.** The opening paragraph stands on its own: say what the subject is and the context a newcomer needs, without assuming the reader has read anything else. For a technical subject, say what it is for and what the reader needs to know first, and say which field it belongs to only if the source places it in one — do not assign a field or category yourself. Do not repeat the title as the definition, and do not pack everything into the first sentence.
- **The lead summarises the body.** Do not state anything in the lead that the body does not support, and keep every qualifier the body keeps: a summary must not turn a hedged or narrower claim into a flat or broader one ("no single X is both necessary and sufficient" is not "no X is necessary or sufficient").
- **Your own words, in the reader's order.** Write the page in your own sentences. Do not carry the source's sentences, or a turn of phrase that is the author's own (as a rough line, a run of more than six words — in a language written without spaces between words, such as Japanese or Chinese, a phrase of similar length), into the body without quotation marks — a page that keeps the source's wording, follows its sections in order and picks up nearly every point reads as a close paraphrase, not a summary. Order the body by what the reader needs — on an entity page, the type's reader questions, with what most readers need first, as Pass 3's "Reader-question body templates" describes (or the type's headings, for a heading-form template); on a view page, what its kind's opening question asks first — not by the order of the source's sections.
  - Quote only when the wording itself matters: a definition or term the source coins, or a claim whose exact wording is the point. Keep it short (about one sentence per quotation), put it in quotation marks, and say whose words they are.
  - Proper names, titles of works, technical terms, figures and code are not wording — use them as the source writes them.
  - Rewording must not change the claim. Keep every qualifier the source keeps, as in "The lead summarises the body" above: putting a point in your own words is not licence to drop a "may", a "in our tests" or a "for small models".
- **Main point first.** Start each section with its main point, then the detail.
- **Headings.** Name each section after what the reader learns about the subject, not after how the source argues. A page about a tool built from a research paper is still a page about the tool: "What it does" and "How it works", not "The problem the authors target" or "How others classify it" as the main sections. If only a sentence or two can be written for a section, fold it into another section instead of giving it a heading.
- **Tables.** When the source describes several items along the same dimensions (a set of components, dimensions, levels, or variants), use a table instead of prose.
- **Examples** help where they help understanding, but only an example the source gives.
- **Terms.** Explain a technical term or acronym the first time it appears, using the source's own explanation — its content, put in your own words unless it is a definition worth quoting under the rule above. If the source does not explain it, link it to its page or leave it unexplained — do not supply an explanation from general knowledge.
- **Reported findings.** When the source reports another work's finding (a cited study, an earlier framework), write it as that work's finding as reported by the source ("an earlier review the authors cite found ..."), not as a plain fact. On an entity page this is the same discipline as Pass 3's "Secondary citation discipline", applied to what a finding says rather than to its date or title.

**Remarks about the page itself: the line is what the remark is about.** A remark about *how this page came to be written* — a source's coverage, what could not be found, which source was used — is out. A remark about *how confident the content is* stays in: "the founding date and the shrine's standing are both recorded by the source as tradition" tells a reader how to read what follows, and would be true in any page written from that material. When unsure, ask whether the sentence would still make sense to someone who did not know WikiCommit generated the page.
