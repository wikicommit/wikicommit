---
wikicommit:
  base: https://schema.org/DefinedTerm
  provenance: default
  granularity:
    - Create a new page for domain-specific terms, jargon, or concepts requiring precise definition
    - Common words with standard meanings do not need a DefinedTerm page
    - Aliases and variant spellings are listed in the aliases frontmatter field, not as separate pages
    - DefinedTerm is a catch-all for abstract terms, jargon, and methodologies that have no more specific Schema.org type (e.g. "vibe coding" — a named approach with no dedicated standard type fits here). It is not the right home for a concrete, named entity (a specific software product, research dataset/benchmark, creative work, standard, etc.) just because the entity happens to also carry a name — for those, check whether a more specific Schema.org standard type (e.g. SoftwareApplication, Dataset, CreativeWork) fits before falling back to DefinedTerm (see wikicommit-generate Pass 2b). This distinction — abstract concept vs. concrete named entity — is domain-independent and applies regardless of the wiki's theme (Issue #447)
    - When multiple sources give the same term differing definitions or origins, if a source can be identified as the one that first coined/proposed the term, treat that as the primary definition; if no such source can be identified, or multiple practically-established usages coexist, present them side by side instead of picking one. Never let a single provider (e.g. a vendor's own official documentation) become the primary definition merely because its material happens to be the source, more structured, or the most recently ingested — that alone is not a reason to outrank other sources
    - When multiple sources describe different concrete implementations or processes that each embody the same broader concept (e.g. several vendors' or projects' own multi-step workflows for the same general idea), do not present any single one of them as if it were the general/default definition of the concept, even if it happens to be the most detailed, the most familiar, or the source ingested first (Issue #451). Describe the concept at the level of generality actually shared across the implementations, and present the differing concrete implementations side by side (or in their own subsections) rather than picking one as the baseline the others are then compared against. This is a distinct axis from the primary-definition rule above — that rule is about *origin* (who coined the term), this one is about *fair framing* when multiple concrete, independently-legitimate implementations of the same concept coexist
title: ""
type: "schema:DefinedTerm"
lang: ""
sources: []
tags: []

properties:
  description: ""
  termCode: ""
  inDefinedTermSet: ""
---

(Precise one-paragraph definition of the term)

## Usage
(how and where the term is used, domain context)

## Related Terms
(links to related [[DefinedTerm/slug]] pages)
