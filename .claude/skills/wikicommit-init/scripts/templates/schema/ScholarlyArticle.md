---
wikicommit:
  base: https://schema.org/ScholarlyArticle
  provenance: default
  granularity:
    - Create a new page for a specific, named academic paper, preprint, or survey that is an independent subject and directly relevant to the wiki's theme
    - A paper mentioned only in passing (e.g. cited alongside several others with no independent discussion of its own findings) is an incidental mention, not an independent subject — do not create a page for it
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - The body should summarize the paper's own contribution (what it studied, what it found/proposed), not walk through the full abstract
    - "properties.keywords is the paper's own declared keyword list, not topics you choose: when the paper has a Keywords section (or its equivalent — Index Terms, Key words, CCS Concepts), copy every entry in the paper's order and wording; when it has none, omit keywords entirely. Subject terms you picked from the content go in tags:, and an arXiv subject classification (e.g. Software Engineering (cs.SE)) is not a keyword"
    - Boundary with NewsArticle/BlogPosting — a ScholarlyArticle is peer-reviewed or preprint academic work (a paper, survey, or dissertation with an abstract and citations) — not journalistic reporting about research (use NewsArticle) and not an informal blog post discussing or summarizing research (use BlogPosting), even when the topic is technical
title: ""
type: "schema:ScholarlyArticle"
lang: ""
sources: []
tags: []

properties:
  description: ""
  author: []
  datePublished: ""
  keywords: []
---

```text
READER QUESTIONS (ScholarlyArticle)
Readers: someone deciding whether to read the paper, or someone who met it cited elsewhere
and wants to know what it found and how far to trust it.
1. What question does it address — the problem or gap it starts from, as the paper states it?
2. What did it do — the method, the data or participants, and the setting?
3. What does it find or propose? Answer this under the fixed `## Key Points` heading below.
4. What do the findings rest on — sample size, setting, study design — and what limitations
   do the authors state?
5. How does it relate to earlier work it builds on or compares itself with?
6. Who wrote it, and where and when was it published — a peer-reviewed venue or a preprint?
```

## Key Points
(one claim per bullet, each a single point the paper itself makes — a finding, a
taxonomy, a stated contribution. Not prose spanning several sentences: a claim that
cannot be lifted out on its own cannot be set beside one on another page, which is what
this section exists for. Keep each bullet to what this paper states — a result it only
cites from other work is that work's claim, and its figures and dates are not
established facts here. Where a claim rests on something narrower than it sounds — one
dataset, one site, a simulation — say so in the same bullet. Keep to the main claims, at
most seven bullets, ordered by importance — not by where the paper raises them: a list
that walks every point in the paper's own order is a second copy of it, not a summary)
