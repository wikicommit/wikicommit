---
wikicommit:
  base: https://schema.org/Person
  provenance: default
  granularity:
    - Create a new page for any person mentioned by full name as an independent subject
    - Use WikiLink [[Person/slug]] in body text for incidental mentions
    - "A person a work of fiction is *about* is an independent subject, not an incidental mention. A narrative states independent facts about its protagonist — what they do, their circumstances, how they are placed in the world — which is exactly the bar the rules below apply; that the person is fictional does not change this (schema:Person covers fictional as well as real people by definition). Create a page for the person a story, novel, or biography is about, and for a named character who recurs across two or more works this wiki covers. Do not create one for the rest of the cast, who act only inside one work's plot without that work being about them — this rule adds at most one page per work plus recurring characters, and is not a licence to promote every named character (Issue #560)"
    - A person named only as a co-author, citation source, or someone else's collaborator within another entity's source — with no independent facts about that person (their own background, views, actions) stated in the source — is an incidental mention, not an independent subject, even though their full name appears; do not create a page for them
    - A single quoted remark or opinion attributed to a person, with no other biographical or contextual information about them in the source, does not by itself meet the "independent facts" bar above — treat it the same as an incidental mention and do not create a page. Independent-subject treatment requires the source to say something about who the person is or does (background, role, actions), not merely to quote a single sentence from them
    - Do not record marital/family relationship properties (spouse, children) or physical attributes (height, weight) even when the source states them — out of scope for this wiki's purpose
    - "For a living individual, keep the page to what that person has themselves made public — works they wrote, talks they gave, positions they say they hold — and leave out biography-shaped facts that would need primary-source verification, such as career history, past employers, and dates of birth, even when the source states them. This is the same judgment the rule above makes about family and physical attributes; the failure it guards against is a person page carrying dates and claims taken from an article that was never itself taken in as a source (Issue #473). It narrows what a page says, never whether the page exists — that is a separate question, answered by .wikicommit/entity-policy.md and off by default. It applies only to the living, so write a historical figure in full (Issue #668)"
    - Boundary — a Person is an individual human. A role, job title, team, or shared account standing for a group is not a person — use Organization for a group that acts as a single actor, and DefinedTerm for a role or title the wiki treats as a concept in its own right
title: ""
type: "schema:Person"
lang: ""
sources: []
tags: []

properties:
  description: ""
  affiliation: "[[Organization/slug]]"
  jobTitle: ""
  birthDate: ""
---

(2-3 paragraph overview of the person)

## Background
(chronological activities, affiliations, and roles. For a living individual, limit this to
roles and activities that person has made public themselves, and omit career history and
past employers)

## Works & Achievements
(major works, projects, awards)
