---
wikicommit:
  # Machine-readable header only. The procedure itself is the prose below.
  # No version field, deliberately: `review-rules.md` carries `rules_version`
  # because a review subagent echoes it back and the orchestrator checks it.
  # Every reader of this file is the agent itself, so an echo would be
  # self-reported and would verify nothing (Issue #886).
  # The `provenance` values the four reading paths stamp, so this list and a written
  # file's own `wikicommit.provenance` are in one vocabulary. The type-necessity pass
  # stamps two of them depending on how the candidate was approved, hence four paths
  # and five values.
  applies_to:
    - init-theme
    - collect
    - generate-interactive
    - generate-auto
    - schema-propose
---

# Writing a `.wikicommit/schema/<Type>.md` file

The one place the procedure for writing a type file is written. Four paths add
types, and each reads this file at the point a candidate has been approved
(Issue #886).

Before this file existed the same procedure lived in four Skills at once. What
they shared was the *procedure*; what differs between them is the *judgment* —
how strong the evidence has to be before proposing a type, how approval is
obtained, and which `provenance` value gets stamped. Those stay with each path,
because the evidence genuinely differs: one has a single sentence of prose, one
a list of candidate titles, one the full text of a source, and one a page that
already exists.

**Do not copy this procedure back into a SKILL.md.** What belongs there is the
threshold, the approval interaction, and the `provenance` value. What belongs
here is how the file is written.

---

## Part 0 — What you are doing, and what you are not

A type has been approved. You are about to create a file that did not exist.

### Add only. Never edit, never delete

This is the one narrow exception to the rule that Skills do not write to
`.wikicommit/schema/`. It permits exactly one thing: creating a file for a type
that has no file yet.

- **Never** edit, overwrite or delete a file that is already there — including
  one written moments ago by the same run, and including a file whose contents
  you think are wrong.
- **Never** commit, and **never** open a pull request. Write the file to disk
  and leave it. The path that called you decides what happens next.

The reason the restriction is this tight is that nothing downstream validates a
schema file, and no Skill can ever edit one afterwards. A file written here is
what that wiki's type selection follows from then on.

### Nothing here is optional because it is small

Type files are rarely written — a run that adds none is the normal outcome — so
each one that *is* written carries disproportionate weight. There is no later
pass that tidies them up.

---

## Part 1 — Choose the properties, then verify every one

### Browse before choosing

Do not name properties from memory of the vocabulary. Ask for the type's full
available set first:

```bash
python .wikicommit/scripts/check_schema_org_type.py --type <Type> --list-properties
```

Each line is `<property><TAB><declaring type><TAB><entity-range candidates, or
"-"><TAB><one-line description>`. Pick 2–6 candidates from that list, chosen
against what the evidence in front of you actually discusses rather than against
the type's definition in the abstract.

### Verify the chosen ones

```bash
python .wikicommit/scripts/check_schema_org_type.py --type <Type> \
  --property "$(cat <<'EOF'
<Prop1>
EOF
)" \
  --property "$(cat <<'EOF'
<Prop2>
EOF
)" \
  ...
```

Each `--property` value goes through its own quote-delimited heredoc. These are
candidate names you just proposed — not values some earlier script already
validated — so they do not qualify for the exemption that lets a verified
identifier be interpolated directly.

Then:

- **The type itself reported `ERROR:`** → drop this candidate entirely. Do not
  write a file for it. Say so: the name did not resolve in the vocabulary, which
  usually means it was misread from a listing.
- **An individual property reported `ERROR:`** → drop that property. **Never**
  put an unverified property name into a `properties:` block.
- **Every candidate property failed** → still write the file, with an empty
  `properties:` block. The type itself is verified as real, and a reviewer or a
  later generation run can add fields by hand. Missing property suggestions is
  not a reason to lose the type.

---

## Part 2 — Write the file

Write it directly with the Write tool, in the standard-type format: a
`wikicommit:` block, template frontmatter with the verified property names
nested under `properties:`, and a body template.

Use `.wikicommit/schema/default.md` (the frontmatter skeleton) and
`.wikicommit/schema/Person.md` (a concrete standard type) as the **fixed** style
references. Do not go looking for a "closest existing type" to copy instead —
these two, always.

### The `wikicommit:` block

| Key | Value |
|---|---|
| `base` | `https://schema.org/<Type>` |
| `provenance` | **the value your own path stamps** — see below |
| `granularity` | 1–3 rules, written per Part 3 |

**`provenance` is yours to set and nobody else's.** Each write site stamps where
the file came from, and the value is permanent — no Skill can change it later.
**Do not copy the `provenance: default` you see in `Person.md`**: that value
belongs to the base types the initializer expands, and copying it would claim
this file was distributed rather than proposed. The path that sent you here names
the value to use.

### The frontmatter template

`title`, `type: "schema:<Type>"`, `lang`, `sources: []`, `tags: []`, then a blank
line and a `properties:` block holding one placeholder per verified property —
an empty string, or an empty list where the property's shape calls for one.

Then a short body template: a 2–3 paragraph overview placeholder and a
`## Details`-style section, following `default.md`'s shape.

---

## Part 3 — Writing `granularity`

This is the one part of the file that is free prose rather than a verified value,
and **nothing downstream checks it**. Frontmatter validation reads only the
required-field list; the vocabulary check verifies that names exist, not that
wording is sound; and the merge path merges the file along with the run's pages.

Write 1–3 rules in the style of `.wikicommit/schema/Person.md` and
`.wikicommit/schema/DefinedTerm.md`, grounded in what the evidence in front of
you actually contained. State when a page of this type should be created, and
when the subject belongs in someone else's page instead.

### One rule must be a `Boundary` rule

Include one rule beginning with `Boundary` that says what the type is *not* for.
Every distributed base type follows this convention, and the reason is
structural: a new type can state its boundary against an existing one, but
**nothing can ever write the reciprocal statement into the existing type's
file**. Without the convention, boundaries accumulate on one side only, and type
selection drifts toward whichever file happens to mention the line.

### Where another installed type is the better home, say so

Name it, as its own rule:

```
Prefer schema:HowTo when the source's substance is an ordered set of steps the reader performs
```

`granularity` is where cross-type deference lives — there is no separate field
for it, and the entity-extraction pass is instructed to follow such a line over
its own read of the fit. Deference is not the same as the `Boundary` rule:
`Boundary` says what the type is not, this says who should have it instead, and a
type can want both.

**Name only types that are actually installed.** A line pointing at a type the
wiki does not have cannot be acted on. This exact kind of line, written at
proposal time, was the one that went unfollowed in a real pilot wiki — so write
it where it applies, and know that it only works if the pass that reads it
honors it.

### A property you deliberately do not want recorded goes here too

If a property that technically applies to the type should not be recorded, say
so as a prose rule — `Do not record <property> even when the source states it —
out of scope for this wiki's purpose` — rather than silently leaving it off the
list with no explanation. There is no field for exclusions.

### Every bullet has to survive YAML parsing as a plain string

Two characters break this, and **they break differently**:

| Written as | What happens | Does anything warn? |
|---|---|---|
| `Boundary: …` | the `": "` turns the bullet into a one-key mapping | one consumer warns; the rest silently skip it |
| `… # …` mid-bullet | opens a YAML comment and truncates the rest of the line | **nothing warns** — the bullet is still a string, the dropped half is simply gone |

So write `Boundary — …` with an em dash, and keep ` #` out of the middle of an
unquoted bullet. If the wording you want needs either character, wrap the whole
bullet in double quotes — the same fix the distributed base-type templates use
(see `.wikicommit/schema/DefinedTerm.md`).

Nothing validates a schema file, so a bullet mangled this way is merged and stays
broken.

### Never contradict a rule stated elsewhere in the pipeline

The known collision is the source-as-entity test that decides whether a source
*document* gets a page of its own: it admits a work with a fixed publication date
and authors, and **excludes** a continuously-updated living resource with no
publication date of its own — an official document, a government procedure page,
an encyclopedia article. A `granularity` saying that official product
documentation qualifies for a page of its own contradicts that head-on.

This exact contradiction was written in a real run and is still in that wiki: the
run only came out right because the agent happened to follow the other rule, and
nothing guarantees the next one will. **When the type you are adding is a kind of
document rather than a kind of subject discussed inside documents, re-read that
test before writing the rule.**

Do not restate general rules that already apply to every type. A `granularity` is
for what is specific to *this* type, and repeating a general rule is how it gets
paraphrased into a contradiction.

### Report a boundary drawn against an installed type

If the `granularity` you wrote states a boundary against a type that already has
a file in `.wikicommit/schema/`, record three things for whatever report the
calling path produces: **the new type name, the installed type it draws the line
against, and the bullet itself**.

You may not write the reciprocal statement into that installed type's file.
Reporting it is the whole remedy — a person can edit `.wikicommit/schema/`
directly, since the write restriction binds Skills and agents rather than people.
Without the report, the boundary exists on one side only and nothing ever says
so.
