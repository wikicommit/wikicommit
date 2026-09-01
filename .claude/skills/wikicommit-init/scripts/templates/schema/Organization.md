---
wikicommit:
  base: https://schema.org/Organization
  provenance: default
  granularity:
    - Create a new page for any organization mentioned by name as an independent subject
    - Subdivisions (departments, teams) share the parent organization page unless they function independently
    - Use WikiLink [[Organization/slug]] in body text for incidental mentions
    - An organization named only as someone's employer or affiliation within another entity's source — with no independent facts about the organization itself (what it does, its history, its role) stated in the source — is an incidental mention, not an independent subject, even though its name appears; do not create a page for it
    - A single sentence describing what an organization does, or a single quoted statement attributed to it, with no other information about its history or role in the source, does not by itself meet the "independent facts" bar above — treat it the same as an incidental mention and do not create a page
    - Do not record membership rosters (employee, member) even when the source lists them — out of scope for this wiki's purpose; mention notable individuals in body prose with a WikiLink instead
    - "Yield to a more specific installed type. Organization sits near the top of a large Schema.org subtree (166 descendant types), so a subject that has a narrower type of its own can always *also* be written as an Organization — correctly, just coarsely. Before choosing Organization, check whether .wikicommit/schema/ already installs a descendant of it that fits the subject better, and use that instead; only reach for Organization when nothing more specific is installed, or when the source does not actually establish the narrower kind. This is about the installed set, not about Schema.org at large — proposing a type that has no file here is a separate step (Issue #565)"
    - Boundary — an Organization is a group that acts as a single actor. Its headquarters, campus, or office is a location rather than the organization itself (use Place), and a product, service, or standard it publishes is not the organization (give that the type which fits the product)
title: ""
type: "schema:Organization"
lang: ""
sources: []
tags: []

properties:
  description: ""
  foundingDate: ""
  foundingLocation: "[[Place/slug]]"
  founder: "[[Person/slug]]"
  url: ""
  numberOfEmployees: ""
---

(2-3 paragraph overview of the organization)

## History
(founding background, major milestones)

## Activities & Products
(core business, notable projects, products or services)
