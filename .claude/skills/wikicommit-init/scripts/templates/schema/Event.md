---
wikicommit:
  base: https://schema.org/Event
  provenance: default
  granularity:
    - Create a new page for events with a specific date and independent significance
    - Recurring events (annual conferences) get one page per edition unless content differs substantially
    - organizer and performer each name an organization or a person; link with a WikiLink ([[Organization/slug]] or [[Person/slug]] as appropriate) when the value independently qualifies for its own page, and write it as plain text otherwise
    - "Yield to a more specific installed type. Event sits near the top of a large Schema.org subtree (35 descendant types), so a subject that has a narrower type of its own can always *also* be written as an Event — correctly, just coarsely. Before choosing Event, check whether .wikicommit/schema/ already installs a descendant of it that fits the subject better, and use that instead; only reach for Event when nothing more specific is installed, or when the source does not actually establish the narrower kind. This is about the installed set, not about Schema.org at large — proposing a type that has no file here is a separate step (Issue #565)"
    - Boundary — an Event is a specific occurrence anchored to a date. A repeatable procedure with no fixed date is not an Event (use HowTo), and a piece of writing reporting on an occurrence is not the occurrence itself (use the article type that fits the writing)
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
  eventStatus: ""
---

(2-3 paragraph overview of the event)

## Overview
(purpose, scale, key participants)

## Outcomes
(results, decisions made, follow-up actions)
