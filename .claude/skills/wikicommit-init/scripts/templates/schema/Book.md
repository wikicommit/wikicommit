---
wikicommit:
  base: https://schema.org/Book
  provenance: default
  granularity:
    - Create a new page for each individual novel or full-length book treated as an independent work
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - "character lists named characters; link each character who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text. The person this work is about qualifies — see Person.md, which treats a work's protagonist as an independent subject rather than an incidental mention. A real living individual this work is the only source about does not qualify yet — Person.md gives them no page while the work is the only source, so list them as plain text (Issue #1341). So does a name already listed in another work page's character property: recurrence across works is evidence this person exists beyond any one plot, so re-evaluate them as a page candidate rather than repeating the plain string. Recurrence is not visible from inside a single generation run, so check_recurring_characters.py reports it afterwards through wikicommit-status (Issue #560)"
    - Do not create a separate page for translations, reprint editions, or individual volumes of a multi-volume work already covered by a parent page; note them in the body instead
    - For a serialized or multi-part work, prefer one page for the whole work over one page per installment unless each installment is independently notable
    - "Open the page by naming the work and saying what kind of work it is — whose book it is and its form or genre (\"<Title> is a detective novel by …\"); for a work of fiction, the form or genre says so. Name the form or genre the source gives; when it gives none, the plain form (a story, a novel) is enough — so that a reader who arrives from a character's or a place's page knows they are reading about a story and not about history"
    - "In a work of fiction, what the work keeps back until late — how it ends, a twist, and in a mystery who did it — is written only in the section that tells the plot, under a heading that says it is the plot. Keep it out of description (which search results and link previews show), the opening paragraphs, the character property and any account of the characters (keep the culprit in the character property, under the name the work first gives them and without marking them as the culprit; name a culprit by the part they play before the reveal — \"the pawnbroker's assistant\" — not as the culprit), and the pages of the work's characters. Inside the plot section, tell the plot through to its end, without a spoiler warning and without holding the ending back. A premise the work itself states at the start — an inverted mystery that shows the crime first — is not something it keeps back. In a collection, this holds for the ending of the frame and of each piece it contains; what the collection announces as it goes — the theme of each part, a heading that tells a piece's outcome in advance — is not kept back"
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
---

```text
READER QUESTIONS (Book)
Readers: someone who met the title in another page or a source and wants to know what the
book is, what is in it, and why the wiki has a page on it.
1. What is this book — its author, its form or genre (a novel, a collection of stories, a
   treatise), and when and where it was written or first published?
2. What is it about — its setting and premise, or for a non-fiction book its subject and
   aim — as a reader meets them at the start, without how it ends?
3. For a work of fiction only: what happens — the plot through to its end, in the section
   that says it is the plot? (The only place the ending is told — see granularity.)
4. For a non-fiction book only: what does it set out, argue, or teach, part by part?
5. How is it put together — parts, volumes, a frame that holds its stories — and for a
   collection, which pieces it contains (a table when there are several)?
6. For a work of fiction only: who are its main characters and what part does each play,
   without what the work keeps back until its end (a table when there are several)?
7. What does it draw on and what does it mean — its sources, themes, and how it is read,
   as the source states them?
8. How has it come down to readers — editions, translations, adaptations — and how has it
   been received?
```
