---
wikicommit:
  base: https://schema.org/BlogPosting
  provenance: default
  granularity:
    - Create a new page for a specific blog post that presents an independently notable argument, technique, or firsthand account directly relevant to the wiki's theme
    - A post mentioned only as a passing citation is not an independent subject — do not create a page for it
    - Prefer extracting the concepts/techniques a post introduces as their own pages (e.g. DefinedTerm, HowTo) over creating a page for the post itself, unless the post's identity as a specific, citable piece of writing (who wrote it, when) is itself relevant to the wiki's theme
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - publisher names a publishing organization; link it with a WikiLink to [[Organization/slug]] the same way author is when it independently qualifies for its own page, and write it as plain text otherwise
    - Boundary with NewsArticle/ScholarlyArticle — a BlogPosting is an individual's or organization's own informal writing (opinion, technique, firsthand account) — not third-party journalistic reporting on an event (use NewsArticle) and not a peer-reviewed or preprint academic work (use ScholarlyArticle), even when the blog covers technical or research topics
title: ""
type: "schema:BlogPosting"
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
READER QUESTIONS (BlogPosting)
Readers: someone deciding whether the post's argument or advice applies to them, or someone
who met a link to it and wants to know what it says.
1. What does the post argue or describe, and who writes it from what position — a
   practitioner, a vendor about its own product, a researcher?
2. What situation or question prompted it?
3. What are its arguments, techniques, or claims? Answer this under the fixed `## Key Points`
   heading below.
4. What does it rest on — the author's own experience, measurements, or the vendor's own
   documentation?
5. When does its advice apply, and what caveats does the author state?
6. What other writing does it respond to or build on, as the post itself says?
```

## Key Points
(one claim per bullet, each a single argument, technique, or claim the post itself
makes. Not prose spanning several sentences: a claim that cannot be lifted out on its
own cannot be set beside one on another page, which is what this section exists for.
Keep each bullet to what this post states — something it only quotes or points to
elsewhere is that source's claim, and its details are not established facts here. Where
the only backing is the author's own experience, or their employer's own product
documentation, say so in the same bullet: a single-source recommendation must never read
as established practice. Keep to the main claims, at most seven bullets, ordered by
importance — not by where the post raises them: a list that walks every point in the
post's own order is a second copy of it, not a summary)
