---
wikicommit:
  base: https://schema.org/NewsArticle
  provenance: default
  granularity:
    - Create a new page for a specific news article that reports an independently notable event, announcement, or development directly relevant to the wiki's theme
    - An article mentioned only as a passing citation, or one that merely aggregates/summarizes other reporting with no independent reporting of its own, is not an independent subject — do not create a page for it
    - The body should summarize what the article reports (the event/announcement and its significance), not walk through the full article
    - Prefer creating pages for the underlying entities the article describes (e.g. a company, a product, a person) over the article itself when the article's only content is routine coverage of an entity that already has (or should have) its own page
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - publisher names a publishing organization; link it with a WikiLink to [[Organization/slug]] the same way author is when it independently qualifies for its own page, and write it as plain text otherwise
    - Boundary with BlogPosting/ScholarlyArticle — a NewsArticle is journalistic reporting by a news publisher/outlet on an event or development (who/what/when, sourced from reporting) — not a peer-reviewed or preprint academic work (use ScholarlyArticle) and not an individual's or company's own blog/opinion writing (use BlogPosting), even when hosted on a news site's blog section
title: ""
type: "schema:NewsArticle"
lang: ""
sources: []
tags: []

properties:
  description: ""
  author: []
  datePublished: ""
  publisher: ""
---

```text
READER QUESTIONS (NewsArticle)
Readers: someone who wants to know what happened, or someone who met the article cited and
wants to know what it reported and on what basis.
1. What does it report — what happened, who was involved, and when and where?
2. Why does it matter, as the article explains it?
3. What facts, figures, and claims does it carry? Answer this under the fixed `## Key Points`
   heading below.
4. Who are its sources — named people, the subject's own statements, documents — and what
   does it say is unconfirmed or disputed?
5. What led up to it, and what does the article say comes next?
6. Which outlet published it, and when?
```

## Key Points
(one claim per bullet, each a single fact, figure, or claim the article itself reports.
Not prose spanning several sentences: a claim that cannot be lifted out on its own
cannot be set beside one on another page, which is what this section exists for. Keep
each bullet to what this article states — something it only attributes to another outlet
is that outlet's claim, and its dates and details are not established facts here. Where
the only backing is one named source, or the subject's own statement, say so in the same
bullet. Keep to the main claims, at most seven bullets, ordered by importance — not by
where the article raises them: a list that walks every point in the article's own order
is a second copy of it, not a summary)
