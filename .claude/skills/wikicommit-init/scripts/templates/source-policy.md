---
wikicommit:
  # Domains never to fetch. Merged with (never replacing) the built-in list in
  # check_extraction_quality.py, which holds the domains static fetching has been
  # confirmed to return an empty shell for. Turning one of those back on would not
  # make it fetchable, so the two lists are unioned rather than overridden.
  # Use this for domains this wiki has decided against, whatever the reason.
  # One host per entry, matched exactly: `example.com` does not cover
  # `blog.example.com`, so list every host you mean. A scheme, a trailing path
  # and a leading `www.` are all stripped before comparing, so `example.com`,
  # `www.example.com` and `https://example.com/` are the same entry.
  exclude_domains: []

  # Domains to read but never register. /wikicommit-collect mines a page on one
  # of these for the primary sources it cites and offers those instead; the page
  # itself never becomes a candidate. Use it for encyclopedias and other indexes
  # whose value here is telling you what exists, not being quoted. Matched the
  # same way as exclude_domains: one host per entry, exact match after stripping
  # a scheme, a path and a leading `www.`.
  index_only: []

  # Sources considered and turned down, so nothing proposes them again. A
  # judgement like "too large to be worth its own page" is not recoverable by
  # reading the source a second time — only a record of the decision keeps it.
  # /wikicommit-collect appends here when you decline a candidate; you can also
  # write entries by hand. Each entry: url (required), reason (required),
  # date (optional, YYYY-MM-DD). Left with no value on purpose rather than as
  # `[]`, so the first entry can be added underneath it without having to
  # rewrite the line first — a flow list and a block entry cannot be mixed, and
  # a syntax error here would take exclude_domains down with it.
  rejected:
---

<!--
What belongs in this file: which sources this wiki takes in, and which it does not.
What does not: which *entities* to write pages about once a source is in — that is
`theme` in .wikicommit/config.yml, and mixing the two makes the entity judgment
read source-selection prose as if it were about entities.

The prose below is read by /wikicommit-generate before it registers a source and by
/wikicommit-collect while it is proposing candidates. Write it as instructions to
someone deciding whether a given document belongs in this wiki. Delete this comment
and these examples once you have written your own; an empty body disables the prose
guidance, exactly as an empty `theme` disables the entity judgment.

Examples of the kind of thing that belongs here:

- Prefer primary sources — official sites, open data, peer-reviewed papers.
- Do not take in personal blogs, advertising, or promotional material for a single
  business.
- Take in one source describing the subject's overall structure first, then work
  outward from it, so later sources have something to attach to.

A shape worth considering when an encyclopedia covers your subject (Issue #570).
It is not a rule and there is nothing to switch on — it is three habits that fit
together:

  1. Take the skeleton from a primary source. In one pilot a city's own overview
     PDF and the city's encyclopedia article produced an identical set of eleven
     area pages, so the encyclopedia was not needed for the skeleton — and a
     primary source carries no share-alike obligation.
  2. Use the encyclopedia as an index: list index_only above, let it tell you
     what exists, and take in the primary sources it cites.
  3. Register the encyclopedia article itself only where no primary source
     exists — a shrine's founding legend, a local custom. Some subjects will
     always be like that; record the license and move on.

The point is not to avoid encyclopedias. It is that a page written from one
encyclopedia article and nothing else tends to be a shorter version of that
article, without its footnotes, that also binds the whole wiki to that article's
license — and this keeps the number of pages in that position small and
deliberate.
-->
