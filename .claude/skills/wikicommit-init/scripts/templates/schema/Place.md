---
wikicommit:
  base: https://schema.org/Place
  provenance: default
  granularity:
    - Create a new page for locations that serve as independent reference points (cities, notable buildings, regions, landmarks)
    - Use WikiLink [[Place/slug]] for incidental geographic mentions
    - "Yield to a more specific installed type. Place sits near the top of a large Schema.org subtree (208 descendant types), so a subject that has a narrower type of its own can always *also* be written as a Place — correctly, just coarsely. Before choosing Place, check whether .wikicommit/schema/ already installs a descendant of it that fits the subject better, and use that instead; only reach for Place when nothing more specific is installed, or when the source does not actually establish the narrower kind. This is about the installed set, not about Schema.org at large — proposing a type that has no file here is a separate step (Issue #565)"
    - "A real place a work of fiction refers to — the work names that town, building, or region and sets its story there — keeps one page, the real place's, and the work's portrayal is a section of it rather than a page of its own. While the work is the page's only source, the page may hold only the portrayal, but its first sentence frames it as the work's (\"In <work>, X is …\") and nothing on the page states the portrayal as the place's own geography or history; those are added when a source about the place comes in. A place the author made up (an invented place) is a separate subject even when modelled on a real one, never a section of the real place's page; when it clears the reference-point bar above and gets a page, that page's first sentence names the work and says the place exists only there. Do not give it a real-world position (containedInPlace, an address) unless the source places it so, and mention the real model only when the source states the relation"
    - Boundary — a Place is a location referred to as a location (where something is). An organization that occupies a location, and an occurrence that happens at one, are not Places — use Organization or Event and reference the location from there with a WikiLink
title: ""
type: "schema:Place"
lang: ""
sources: []
tags: []

properties:
  description: ""
  containedInPlace: "[[Place/slug]]"
---

```text
READER QUESTIONS (Place)
Readers: someone who met the place name in another page and wants to know what and where
it is, and why it matters to this wiki's subject — a real place, or one that exists only
in a work.
1. What and where is it — what kind of place, and where it lies? For an invented place,
   which work it belongs to, and that it exists only there.
2. Why does it matter to this wiki's subject — what happened there, who lived or worked
   there, what it is known for?
3. What is it like — its layout, landscape, buildings, or parts, as the source describes
   them?
4. For a real place only: what is its history, as far as the source tells it?
5. For a real place only: what can a visitor find there now, and how is it reached — only
   as the source gives it?
6. For a real place a work of fiction portrays only: how does the work portray it? Keep
   this apart from what the page says of the place itself.
7. For an invented place only: what part does it play in the work, and what real place is
   it modelled on, if the source says?
```
