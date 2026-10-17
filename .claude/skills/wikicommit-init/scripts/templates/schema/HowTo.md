---
wikicommit:
  base: https://schema.org/HowTo
  provenance: default
  granularity:
    - Create a new page for each distinct procedure or instructional sequence
    - Sub-steps that cannot be performed independently stay within the parent HowTo page
    - The `tool` property lists what the reader uses to carry out the steps — software, a service, equipment — and is often empty; a procedure that needs no named tool is still a HowTo. Leave it out rather than treating its emptiness as a signal that the subject does not belong to this type
    - "Write the steps as a numbered list in the order the reader performs them, keeping the steps as the source divides them; nest a sub-step under its step. Do not turn the steps into prose or regroup them by topic — the order is the answer. A choice between ways of doing a step stays inside that step; a whole alternative procedure is a separate list under its own heading. When the source says what to do without giving an order, do not supply one: list the actions without numbers"
    - Boundary — a HowTo is the sequence of steps the reader performs to reach one outcome, ordered whenever the source orders them. Explanatory, reference, or descriptive material about a subject is not a step sequence and does not belong here, even when it is instructional in tone or happens to contain a numbered list; give that material the type that fits its subject instead. Conversely, when a source's substance *is* the ordered steps, prefer a HowTo page over burying those steps inside the page for the service, product, or concept they operate on
title: ""
type: "schema:HowTo"
lang: ""
sources: []
tags: []

properties:
  description: ""
  tool: []
---

```text
READER QUESTIONS (HowTo)
Readers: someone who wants to do what this procedure does, or to know whether it is the
procedure they need — and who will follow it step by step.
1. What does this procedure achieve, for whom, and who sets it out (the authority or author
   whose procedure it is)?
2. When does it apply — the situation or problem it is for, and what it does not cover?
3. What is needed before starting — conditions to meet, tools, access, prior knowledge?
4. What are the steps, in order? (A numbered list, unless the source gives no order —
   see granularity.)
5. How does the reader know it worked — the result to expect, or how to check it?
6. What can go wrong, and what then — warnings, common mistakes, troubleshooting, as the
   source gives them?
7. What variations does it allow — alternatives for other settings, tools, or scales?
```
