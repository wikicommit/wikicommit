---
wikicommit:
  base: https://schema.org/ShortStory
  provenance: default
  granularity:
    - Create a new page for each individual short story or novella treated as an independent work
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - "character lists named characters; link each character who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text. The person this work is about qualifies — see Person.md, which treats a work's protagonist as an independent subject rather than an incidental mention. So does a name already listed in another work page's character property: recurrence across works is evidence this person exists beyond any one plot, so re-evaluate them as a page candidate rather than repeating the plain string. Recurrence is not visible from inside a single generation run, so check_recurring_characters.py reports it afterwards through wikicommit-status (Issue #560)"
    - Do not create a separate page for translations or reprint editions of the same story; note them in the body instead
    - Boundary — a ShortStory is a single short-form work of fiction. A full-length work, and a collection published as one volume, are not ShortStories (use Book) — create ShortStory pages for the individual pieces such a collection contains when each is independently notable
title: ""
type: "schema:ShortStory"
lang: ""
sources: []
tags: []

properties:
  description: ""
  author: []
  datePublished: ""
  character: []
  genre: ""
---

(2-3 paragraph overview of the story: setting, premise, and its significance)

## Plot Summary
(concise summary of the plot, without reproducing the original text)

## Characters & Publication
(main characters, first publication venue and date, notable adaptations or context)
