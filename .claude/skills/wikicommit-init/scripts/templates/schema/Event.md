---
wikicommit:
  base: https://schema.org/Event
  provenance: default
  granularity:
    - Create a new page for events anchored to dates (a single occurrence, or one that recurs on dates the source states) and with independent significance
    - "A recurring event gets one page for the event itself, named without a year (Urawa Matsuri, not Urawa Matsuri (2026)). A reader meets the name of the event, not of one year's edition, and a source that lists each year's dates (an annual events calendar) says nothing about an edition that would not also belong on the event's page. Give one edition a page of its own only when a source is about that edition — what happened at it, who took part, what came of it — and name it with its year like any other edition (`-<year>` at the end of the slug, `（<year>）` or a space and `(<year>)` at the end of the title). The event's page and an edition's page are broader and narrower pages, not a series: the event's page stands on its own sources. When the two are listed as a name collision, relate them as broader (the event's page contains the edition's), not as series, which would rename the event's page with a year"
    - "Treat an event as recurring only when the source says it recurs (held every year, the 54th edition). A name that only suggests an edition (\"2025 Winter\") is not enough: write it as a single event and skip question 6"
    - "When the source's subject is a name that gathers several separate events (one summer festival name covering seven local festivals), write one page for that name and list its events on it (question 8). Give one of those events a page of its own only when the source states something about it besides its date, time and place"
    - "startDate and endDate belong to one occurrence. Fill them on the page for a single event or for one edition, and leave them out on the page for a recurring event or a name that gathers several events — there they could only be this year's dates, a value that needs a qualifier, which stays in the body. When such a page's body gives this year's schedule, set expires_at to the first date in that schedule: from then on part of the schedule is past, and the page needs this year's schedule checked"
    - organizer and performer each name an organization or a person; link with a WikiLink ([[Organization/slug]] or [[Person/slug]] as appropriate) when the value independently qualifies for its own page, and write it as plain text otherwise
    - "Yield to a more specific installed type. Event sits near the top of a large Schema.org subtree (35 descendant types), so a subject that has a narrower type of its own can always *also* be written as an Event — correctly, just coarsely. Before choosing Event, check whether .wikicommit/schema/ already installs a descendant of it that fits the subject better, and use that instead; only reach for Event when nothing more specific is installed, or when the source does not actually establish the narrower kind. This is about the installed set, not about Schema.org at large — proposing a type that has no file here is a separate step (Issue #565)"
    - Boundary — an Event is an occurrence anchored to dates — a single occurrence, or one that recurs on dates the source states. A repeatable procedure with no fixed date is not an Event (use HowTo), and a piece of writing reporting on an occurrence is not the occurrence itself (use the article type that fits the writing)
title: ""
type: "schema:Event"
lang: ""
sources: []
tags: []

properties:
  description: ""
  startDate: ""
  endDate: ""
  location: ""
  organizer: ""
  performer: ""
---

```text
READER QUESTIONS (Event)
Readers: someone who met the name of the event in another page or a source — a conference,
a festival, an outbreak, a battle — and wants to know what it was, what happened, and why
the wiki has a page on it.
1. What is this event — what kind of occurrence it is, when and where it takes or took
   place, and, for an organized event, who organizes or organized it?
2. Why did it happen, or what is it for — its purpose, or the circumstances that led to it?
3. What happens or happened — its programme or its course, in order (a table for a
   schedule or for several parts along the same dimensions)?
4. Who took part, and at what scale — speakers, performers, participants, those affected?
5. What came of it — results, decisions, follow-up, consequences, as the source reports
   them?
6. For a recurring event only (the source says it recurs): how often and since when is
   it held, and how do its editions differ?
7. How has it been recorded and remembered — the accounts and works that describe it, and
   how it is read, as the source states them?
8. For a name that gathers several separate events only: which events does it cover —
   each with when and where it takes place (a table)?
```
