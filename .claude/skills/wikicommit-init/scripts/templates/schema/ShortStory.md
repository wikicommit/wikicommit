---
wikicommit:
  base: https://schema.org/ShortStory
  provenance: default
  granularity:
    - Create a new page for each individual short story or novella treated as an independent work
    - author lists multiple names; link each author who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text
    - "character lists named characters; link each character who independently qualifies for their own [[Person/slug]] page with a WikiLink, and list others as plain text. The person this work is about qualifies — see Person.md, which treats a work's protagonist as an independent subject rather than an incidental mention. A real living individual this work is the only source about does not qualify yet — Person.md gives them no page while the work is the only source, so list them as plain text (Issue #1341). So does a name already listed in another work page's character property: recurrence across works is evidence this person exists beyond any one plot, so re-evaluate them as a page candidate rather than repeating the plain string. Recurrence is not visible from inside a single generation run, so check_recurring_characters.py reports it afterwards through wikicommit-status (Issue #560)"
    - Do not create a separate page for translations or reprint editions of the same story; note them in the body instead
    - "Open the page by naming the work and saying what kind of fiction it is — whose story it is and its form or genre (\"<Title> is a detective story by …\"). Name the form or genre the source gives; when it gives none, the plain form (a story, a novel) is enough — so that a reader who arrives from a character's or a place's page knows they are reading about a story and not about history"
    - "What the work keeps back until late — how it ends, a twist, and in a mystery who did it — is written only in the section that tells the plot, under a heading that says it is the plot. Keep it out of description (which search results and link previews show), the opening paragraphs, the character property and any account of the characters (keep the culprit in the character property, under the name the work first gives them and without marking them as the culprit; name a culprit by the part they play before the reveal — \"the pawnbroker's assistant\" — not as the culprit), and the pages of the work's characters. Inside the plot section, tell the plot through to its end, without a spoiler warning and without holding the ending back. A premise the work itself states at the start — an inverted mystery that shows the crime first, or a heading that tells the outcome in advance — is not something it keeps back"
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

```text
READER QUESTIONS (ShortStory)
Readers: someone who met the title in another page or a source — often the page of a
character, an author, or the collection it belongs to — and wants to know what the story
is, what happens in it, and why the wiki has a page on it.
1. What is this story — its author, its form or genre, and when and where it first appeared
   (a magazine, or the collection it was written for)?
2. What is it about — its setting and premise, as a reader meets them at the start, without
   how it ends?
3. What happens — the plot through to its end, in the section that says it is the plot?
   (The only place the ending is told — see granularity.)
4. Who are its main characters and what part does each play, without what the story keeps
   back until its end (a table when there are several)?
5. Where does it stand — in the collection or frame it belongs to, or among the author's
   other works with the same characters?
6. What does it draw on and what does it mean — its sources, themes, and how it is read, as
   the source states them?
7. How has it come down to readers — later editions, translations, adaptations, readings —
   and how has it been received?
```
