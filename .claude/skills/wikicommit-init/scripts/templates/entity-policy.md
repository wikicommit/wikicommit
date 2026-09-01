---
wikicommit:
  # Do not write pages about living individuals. With this on, /wikicommit-generate's
  # entity-extraction pass drops such an entity as `action: exclude` with
  # `exclude_reason: privacy`, automatically and without asking — the same way an
  # off-`theme` entity is dropped. Off by default: leave it `false` and every entity is
  # generated as before, exactly as an empty `theme` disables the relevance judgment.
  # Whether someone is living is judged by the LLM, as `theme` is: the switch is
  # configuration, the judgment is not. Exceptions go in the prose below, not here.
  exclude_living_persons: false
---

<!--
What belongs in this file: whether an entity may be written about at all.
What does not: whether it is *relevant* — that is `theme` in .wikicommit/config.yml.

The two are different axes and both are read by the same entity-extraction pass:

  theme                 relevance    — has this anything to do with what the wiki covers?
  this file             permissibility — granted it does, should a page exist for it?

A living person at the very centre of the subject scores highest on relevance and may
still be one you do not want a page about. That is why this is not a line in `theme`:
mixing them makes the relevance judgment read permissibility prose as if it were about
relevance, and vice versa.

The prose below is free text — the switch above is not the only thing this file can
say, and a category you write here needs no new key. Write it as instructions to
someone deciding whether a page should exist for a given subject. Delete this comment
and these examples once you have written your own; an empty body means no prose policy.

Categories worth considering, none of which the switch above covers on its own:

- Real individuals who are not public figures. Official documents routinely carry
  the names of advisory-committee members, permit holders and petitioners. This is
  usually the one that does the most work: "living" is a defensible line, but the one
  that actually separates risk is whether someone is a public figure. A deceased
  private individual (an ordinary resident named in a local history) is not covered by
  the switch; a living public figure is covered by it more than you may want.
- Real minors. A wiki covering schools or neighbourhood events will meet this.
- Matters under dispute, and events still unfolding. These are Event-shaped, not
  Person-shaped, so the switch never touches them. `expires_at` handles "this will go
  out of date"; it does not handle "this should not be written yet".
- Your own organization's unreleased information. Nothing else in WikiCommit knows
  what has and has not been announced.

Do not over-exclude. In one pilot, `theme` alone was used to keep people out and the
wiki ended up with zero Person pages — including three historical figures (died 1486,
1738 and 1830) repeatedly named in its own body text, whom there was never any reason
to withhold. Only one of the four people dropped was a living public figure. The more
categories you add here, the more this direction pulls, so say who is *in* as plainly
as who is out: public figures acting in their public capacity, and historical figures,
normally belong in the wiki.

Two things do not belong here, because they already have a home:

- Advertising, promotional material, and personal blogs — these are about which
  *sources* to take in. See .wikicommit/source-policy.md.
- Copyright and licensing — settled at the source, via each source's recorded
  license and the share-alike warning at registration time. Writing it again here
  splits one decision across two files.

This policy applies when a page is generated, and does not reach back. Turning the
switch on, or adding a category, does not remove pages that already exist — the
regeneration mode does not re-run the entity-extraction pass, so nothing re-judges
them. To take an existing page down, use /wikicommit-remove (with
`removed_reason: gdpr` where that is the reason).
-->
