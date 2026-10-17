---
wikicommit:
  base: https://schema.org/DefinedTerm
  provenance: default
  granularity:
    - Create a new page for domain-specific terms, jargon, or concepts requiring precise definition
    - Common words with standard meanings do not need a DefinedTerm page
    - Aliases and variant spellings are listed in the aliases frontmatter field, not as separate pages
    - "When a source groups terms into a named classification scheme (a taxonomy, a set of levels, a spectrum), record the membership in the `tags` frontmatter field and explain the scheme itself in the body — do not add a `properties:` key for it. Schema.org's own slot for this, `inDefinedTermSet`, accepts only a `DefinedTermSet` entity or a URL identifying one, and a scheme that exists only inside this wiki has neither, so the key was dropped from this template rather than left as a placeholder nothing could fill (Issue #553)"
    - "DefinedTerm ends up covering three different kinds of subject at once — a phenomenon or problem, a mechanism or component, and a practice or method — because Schema.org has no general type for the third (Issue #551). When the subject is a practice or method (a technique someone applies to get an outcome, as opposed to a thing that simply is the case), the body must state four things the other two kinds do not need: the conditions under which it applies, what it assumes is already in place, how it fails or is misapplied, and how well-established it is — who proposed it and on what basis (one person's report, a widely-repeated convention, a measured result). Gather these in one place (reader question 6 of the body template) rather than scattering them through the definition, so that a reader can tell a well-grounded practice from one someone suggested once. Skip that question entirely for the other two kinds"
    - "Boundary — DefinedTerm is a catch-all for abstract terms, jargon, and methodologies that have no more specific Schema.org type (e.g. \"vibe coding\" — a named approach with no dedicated standard type fits here). It is not the right home for a concrete, named entity (a specific software product, research dataset/benchmark, creative work, standard, etc.) just because the entity happens to also carry a name — for those, check whether a more specific Schema.org standard type (e.g. SoftwareApplication, Dataset, CreativeWork) fits before falling back to DefinedTerm (see wikicommit-generate Pass 2b). This distinction — abstract concept vs. concrete named entity — is domain-independent and applies regardless of the wiki's theme (Issue #447)"
    - When multiple sources give the same term differing definitions or origins, if a source can be identified as the one that first coined/proposed the term, treat that as the primary definition; if no such source can be identified, or multiple practically-established usages coexist, present them side by side instead of picking one. Never let a single provider (e.g. a vendor's own official documentation) become the primary definition merely because its material happens to be the source, more structured, or the most recently ingested — that alone is not a reason to outrank other sources
    - "When multiple sources describe different concrete implementations or processes that each embody the same broader concept (e.g. several vendors' or projects' own multi-step workflows for the same general idea), do not present any single one of them as if it were the general/default definition of the concept, even if it happens to be the most detailed, the most familiar, or the source ingested first (Issue #451). Describe the concept at the level of generality actually shared across the implementations, and present the differing concrete implementations side by side (or in their own subsections) rather than picking one as the baseline the others are then compared against. This is a distinct axis from the primary-definition rule above — that rule is about *origin* (who coined the term), this one is about *fair framing* when multiple concrete, independently-legitimate implementations of the same concept coexist"
title: ""
type: "schema:DefinedTerm"
lang: ""
sources: []
tags: []

properties:
  description: ""
---

```text
READER QUESTIONS (DefinedTerm)
Readers: someone who has just met the term, or someone who wants to tell it apart from a
similar one.
1. What does it mean — what broader kind of thing it is, and what sets it apart from others of
   that kind?
2. Where does it come from and where is it used — who proposed it, in what field, and for what
   purpose?
3. What is it made of — its components, dimensions, levels, or variants, if the source breaks it
   down (a table when there are several along the same dimensions)?
4. What is an example of it, as given by the source?
5. How does it differ from similar or easily confused terms the source mentions?
6. For a practice or method only: when does it apply, what does it assume, how does it fail,
   and how well established is it?
```
