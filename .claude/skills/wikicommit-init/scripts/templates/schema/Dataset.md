---
wikicommit:
  base: https://schema.org/Dataset
  provenance: default
  granularity:
    - Create a page for a specific, named dataset, benchmark, corpus, or survey that the source describes as a subject in its own right — stating what it contains, how it was assembled, or where it is published — rather than only using it as the material for an experiment
    - A dataset named only as the input to a study, with no account of its own contents or provenance, is an incidental mention — name it in the citing page's body and do not create a page for it
    - "Boundary — a Dataset is the body of structured data itself, not the paper that introduces, analyses, or reports results from it. Prefer schema:ScholarlyArticle for the paper and link the two with a WikiLink; figures a paper computes from a dataset (one model's score on it, say) are that paper's findings, not attributes of the dataset"
    - "variableMeasured lists the fields one record carries, as short plain-text names: the columns of a table, the variables a survey measures, or the parts of one benchmark instance (its input, its expected output or label, the tests that judge it). An evaluation metric or a statistic computed over the records is not a field. A field name is not an entity — do not WikiLink it. Leave the key out for a collection whose records have no fields to name (a corpus of free text, say)"
    - "creator is whoever assembled the dataset; link it with a WikiLink to [[Organization/slug]] or [[Person/slug]] when that party independently qualifies for its own page, and write it as plain text otherwise"
title: ""
type: "schema:Dataset"
lang: ""
sources: []
tags: []

properties:
  description: ""
  creator: []
  url: ""
  variableMeasured: []
  temporalCoverage: ""
---

```text
READER QUESTIONS (Dataset)
Readers: someone choosing a dataset to evaluate or train with, or someone who met its name
in a paper and wants to know what is inside.
1. What is it for — what task or ability does it measure or train, and why was it built
   (what gap in earlier datasets does it fill)?
2. What does one record (instance) consist of — its inputs, the expected output or label,
   and the fields it carries?
3. How big is it and what does it cover — counts, languages, domains, time span, splits?
4. How was it built — where the raw material came from, how it was filtered or annotated,
   and how quality was checked?
5. How is it used for evaluation — the metric, the harness or procedure, and what counts as
   success?
6. Where is it published and under what terms?
7. What are its known limitations or biases, as stated by the source?
8. How does it differ from related datasets the source compares it with?
```
