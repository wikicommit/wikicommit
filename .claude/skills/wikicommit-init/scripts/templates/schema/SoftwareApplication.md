---
wikicommit:
  base: https://schema.org/SoftwareApplication
  provenance: default
  granularity:
    - Create a new page for any named software application, tool, IDE, CLI, extension, library, or hosted service treated as an independent subject
    - A tool named only in passing as part of another subject's setup, tech stack, or list of alternatives, with no independent facts about the tool stated in the source, is an incidental mention, not an independent subject — WikiLink it in body text if it has a page, and do not create one for it
    - Prefer schema:HowTo when the source's substance is an ordered set of steps the reader performs, even when those steps are performed with one named tool throughout. The workflow is the HowTo, and the tool it uses keeps its own page here
    - Prefer schema:DefinedTerm when the subject is a methodology, practice, or piece of terminology rather than a piece of software someone runs, even where a single tool popularized it
    - Prefer schema:Organization for the company, lab, or team that publishes a tool. The vendor and the product are separate subjects; link them through the author property rather than folding the vendor into the product page
    - "author names who makes the software; link it with a WikiLink to [[Organization/slug]] or [[Person/slug]] when that party independently qualifies for its own page, and write it as plain text otherwise"
    - "Say in the body which version each behavior was observed in, where the source states one. Software changes between the source's publication and the reader's visit, and an undated statement of what it does quietly stops being true. This template has no version key for the same reason: a version number on its own is a fact with a hidden date"
    - Do not record pricing, plan tiers, or download counts even when the source states them — they go stale before a reader arrives. A result the source reports (a benchmark score, say) belongs in the body, attributed to the study or report that measured it, never in properties
    - Boundary — a SoftwareApplication is software someone runs. A specification, protocol, file format, API convention, or model weights release is not an application; use DefinedTerm for a concept or format, and reserve this type for something installable, invocable, or hosted
title: ""
type: "schema:SoftwareApplication"
lang: ""
sources: []
tags: []

properties:
  description: ""
  applicationCategory: ""
  featureList: []
  author: []
  url: ""
---

```text
READER QUESTIONS (SoftwareApplication)
Readers: someone deciding whether to use the tool, or someone who met its name in a paper
or a post and wants to know what it is.
1. What is it — what kind of software, what problem it solves, and who makes it?
2. How does it work — the approach or architecture that distinguishes it?
3. How is it used — how it is installed or invoked, and what a user gives it and gets back?
4. What can it do and not do — its capabilities and stated limitations, with the version where
   the source states one?
5. How well does it work — results the source reports, attributed to the study or report that
   measured them?
6. How does it differ from tools the source compares it with?
7. Where is it used in practice — concrete deployments the source describes, each presented as
   that organisation's use, not as the tool's general behaviour?
```
