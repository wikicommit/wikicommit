---
wikicommit:
  base: https://schema.org/Book
  provenance: default
  granularity:
    - Create a new page for each individual novel or full-length book treated as an independent work
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - "character lists named characters; link each character who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text. The person this work is about qualifies — see Person.md, which treats a work's protagonist as an independent subject rather than an incidental mention. So does a name already listed in another work page's character property: recurrence across works is evidence this person exists beyond any one plot, so re-evaluate them as a page candidate rather than repeating the plain string. Recurrence is not visible from inside a single generation run, so check_recurring_characters.py reports it afterwards through wikicommit-status (Issue #560)"
    - Do not create a separate page for translations, reprint editions, or individual volumes of a multi-volume work already covered by a parent page; note them in the body instead
    - For a serialized or multi-part work, prefer one page for the whole work over one page per installment unless each installment is independently notable
    - Boundary — a Book is a full-length work published as a book. A short story or novella is not a Book even when it appears inside one (use ShortStory, and note the containing volume in that page's body); a collection published as a volume is itself a Book
title: ""
type: "schema:Book"
lang: ""
sources: []
tags: []

properties:
  description: ""
  author: []
  datePublished: ""
  character: []
  genre: ""
  isbn: ""
---

(2-3 paragraph overview of the book: setting, premise, and its significance)

## Plot Summary
(concise summary of the plot, without reproducing the original text)

## Characters & Publication
(main characters, first publication venue and date, notable adaptations or context)
