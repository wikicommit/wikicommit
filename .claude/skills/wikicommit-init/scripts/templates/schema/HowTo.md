---
wikicommit:
  base: https://schema.org/HowTo
  provenance: default
  granularity:
    - Create a new page for each distinct procedure or instructional sequence
    - Sub-steps that cannot be performed independently stay within the parent HowTo page
    - The `tool` and `supply` properties suit physical procedures and are frequently empty; a procedure that needs neither is still a HowTo. Leave them out rather than treating their emptiness as a signal that the subject does not belong to this type
    - Boundary — a HowTo is an ordered sequence of steps the reader performs to reach one outcome. Explanatory, reference, or descriptive material about a subject is not a step sequence and does not belong here, even when it is instructional in tone or happens to contain a numbered list; give that material the type that fits its subject instead. Conversely, when a source's substance *is* the ordered steps, prefer a HowTo page over burying those steps inside the page for the service, product, or concept they operate on
title: ""
type: "schema:HowTo"
lang: ""
sources: []
tags: []

properties:
  description: ""
  totalTime: ""
  tool: []
  supply: []
---

(1-2 sentence overview of what this procedure accomplishes)

## Prerequisites
(tools, materials, prior knowledge required)

## Steps
1. (step description)
2. (step description)

## Notes
(warnings, variations, troubleshooting tips)
