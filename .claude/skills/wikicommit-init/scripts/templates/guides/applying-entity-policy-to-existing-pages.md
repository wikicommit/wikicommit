# Applying an entity policy to pages that already exist

`.wikicommit/entity-policy.md` is read while a page is being generated, and nowhere else. So
turning `exclude_living_persons` on — or writing a category into the prose body, or loosening
either back again — changes what the *next* run produces and leaves everything already on disk
exactly as it was.

One command puts the affected sources back in the queue. Everything past that is judgment, and
the second half of this guide is about that half.

> **These guides are written in English only, and that is a deliberate exception.** Everything
> else WikiCommit shows a human follows the reader: a review-tracking Issue is rendered in the
> wiki's `primary_lang`, while a script's diagnostics stay in English because their reader is the
> operator or an agent. A guide's reader is a human operator, so that rule would put it in
> `primary_lang` — but a guide is a *distributed file*, not text an agent renders on the spot, so
> honouring it would mean carrying one template per language. `.wikicommit/review-rules.md` is
> already distributed in English for the same practical reason. Written here so the next person to
> touch this does not reopen the question as a bug.

> **This directory is WikiCommit's, not yours.** Every later `/wikicommit-init` and
> `/wikicommit-update` overwrites what is here, so an edit you make to a guide is lost on the next
> refresh, and a file of your own added alongside them is reported as an orphan by
> `/wikicommit-status` and offered for deletion by `/wikicommit-update`. Keep your own notes
> somewhere else in the repository.

## The one command

```
/wikicommit-reconcile --all
/wikicommit-generate
```

`/wikicommit-reconcile` generates nothing. It sets `status: pending` on the management files you
selected, and the next `/wikicommit-generate` collects them through the rule it already had. That
second run is what re-reads the policy, because the entity-extraction pass is the only place the
policy is read at all.

Queuing happens in one go; generating may not. Above five queued sources `/wikicommit-generate`
stops and asks whether to take all of them or only the first five, and the ones it leaves stay
queued — so run it again until nothing is waiting. `/wikicommit-status` counts what still is.

**`/wikicommit-generate --regenerate` does not do this.** The regeneration mode rebuilds a page
from its own sources and deliberately skips the extraction pass, so it never re-judges whether the
page should exist. That is why the requeue exists.

**This applies to the prose body as much as to the switch.** A category you wrote yourself
— private individuals, minors, matters under dispute, your organization's unreleased information —
is read by the same pass, in the same way, and produces the same exclusion. There is nothing
special about the switch that makes only it reach back.

Requeuing leaves the recorded hash alone, so a URL source whose fetch is still in the local cache
is read from there rather than downloaded again. Changing a policy does not mean re-downloading the
web — on the machine that fetched it. That cache is not part of the repository, so on a fresh clone
or a second machine every URL source is fetched afresh, and one whose remote content has changed
since is rebuilt against what it says today. If that is not what you wanted from a policy change,
requeue on the checkout that holds the cache.

## Choosing a selector

`--all` is the right default here. A policy is not scoped to a type, so neither is its effect.

**`--type <Type>` cannot see the sources that matter when you loosen a policy.** That selector
matches on the pages a source produced, and a source excluded in full produced none — so the very
sources that a loosened policy would now let through are the ones it is structurally unable to
select. If you have just turned the switch off, or deleted a category from the prose, use `--all`,
or `--source` naming them one at a time.

`--source <path|url>` takes one source, named the way it was registered.

## What the command does not settle

### Pages that already exist are not removed

Nothing in the generation path deletes a page. Requeue with the switch on, and the extraction pass
may now drop that entity — the page written under the old policy stays on disk, published, exactly
where it was. `/wikicommit-remove` is the only route that takes a page down; use
`removed_reason: gdpr` where that is the reason.

This is the single most important line in this guide. A policy about what may be written about is
easy to read as a policy about what is on the site, and it is not one.

### A page the run rewrites goes back to unread

The pass does not only decide whether an entity still belongs. For every entity it keeps, it writes
the page again from the source — so a page a person had read comes back changed, its review status
returns to pending and the reviewer's name is dropped with it. The published banner stops saying a
person read that page, and the next `/wikicommit-merge` opens a fresh review-tracking Issue for each
one. A page that comes out byte-identical keeps both, but expect that to be the exception.

So `--all` is cheap to type and not cheap to run on a wiki whose pages have been read. Where you
know which sources a policy change can touch, name them with `--source` instead; where you do not,
`--all` is still the right answer — just expect the reading to be asked for again.

### The run names the pages for you

When the generating run excludes an entity that already has a page, it says which page: the run's
own completion notice lists it, and each management file's `## Generation Notes` keeps a copy. So
read either one — there is no need to work the paths out yourself.

It reads as a statement of fact, and that is deliberate: the page exists, and that run did not
create or update it. **That is not the same as saying it should go.** A page can rest on several
sources, and one of them ruling the entity out today says nothing about the others. Only entries
excluded on the policy's own grounds point at `/wikicommit-remove`; an entity that merely fell
outside the wiki's subject is reported and left alone.

If you are looking at a run from before this — the paths were not reported then — the titles in
`## Generation Notes` are what you have, and they do not give you the file names: those are
language-neutral English identifiers, and the rule that makes one from a title does not run
backwards, so a Japanese title does not tell you the slug. The `generated_pages` list in the same
file would have named them outright, but it no longer holds the dropped ones — a source excluded in
full carries no list at all afterwards, and a partly excluded one lists only what it still
produced. The version from before the run is in the repository's history: `git show HEAD:<management
file>` while the change is uncommitted, or `git log -p -- <management file>` after.

### Some places the switch cannot reach

The switch is worded about persons, but a person appears in more than the `Person` type: an
organization whose substance is one individual or a handful, an event's organizer, a story's
character. A rule that crosses types cannot live in a type template either — nothing writes into
an existing one. The prose body of the policy file is where such a rule goes, and reviewing those
other types is on you.

### Do not over-exclude

In one pilot wiki, relevance alone was used to keep people out and the result was zero `Person`
pages — including three historical figures (died 1486, 1738 and 1830) named repeatedly in the
wiki's own body text, whom there was never any reason to withhold. Only one of the four people
dropped was a living public figure.

Requeuing works in this direction too, and this is where it earns its place: loosen the policy,
requeue, and the pass that dropped them runs again. Say who is *in* as plainly as who is out —
public figures acting in their public capacity, and historical figures, normally belong in a wiki.

### Nothing reports this to you on a schedule

No health check lists "pages this policy would now exclude". That is a decision rather than an
omission, and it is worth knowing why, so that the absence does not read as a gap:

1. **There would be no evidence on one side of it.** A report like that joins "the switch is on"
   against "this page is a `Person`" — and the second half is not evidence of anything. The
   candidate set would be every page under `Person/`, which you can already list.
2. **Doing the right thing would not clear it.** For most of those pages the correct action is to
   keep them. A finding that stays lit after you have handled it correctly is a finding people
   learn to skip, and skipping spreads to the findings that do matter.
3. **It would push the wrong way.** Presenting every `Person` page as a policy candidate pulls
   toward exactly the over-exclusion the section above warns about.
4. **It would fire once.** Changing a setting is a single event, and a standing check is the wrong
   shape for one.

The one thing a machine could tell you here is that the switch is on, and you are the person who
turned it on.
