---
wikicommit:
  base: https://schema.org/Place
  provenance: default
  granularity:
    - Create a new page for locations that serve as independent reference points (cities, notable buildings, regions, landmarks)
    - Use WikiLink [[Place/slug]] for incidental geographic mentions
    - "Yield to a more specific installed type. Place sits near the top of a large Schema.org subtree (208 descendant types), so a subject that has a narrower type of its own can always *also* be written as a Place — correctly, just coarsely. Before choosing Place, check whether .wikicommit/schema/ already installs a descendant of it that fits the subject better, and use that instead; only reach for Place when nothing more specific is installed, or when the source does not actually establish the narrower kind. This is about the installed set, not about Schema.org at large — proposing a type that has no file here is a separate step (Issue #565)"
    - Boundary — a Place is a location referred to as a location (where something is). An organization that occupies a location, and an occurrence that happens at one, are not Places — use Organization or Event and reference the location from there with a WikiLink
title: ""
type: "schema:Place"
lang: ""
sources: []
tags: []

properties:
  description: ""
  address: ""
  latitude: ""
  longitude: ""
  containedInPlace: "[[Place/slug]]"
  url: ""
---

(2-3 paragraph overview of the place)

## Geography & Access
(location details, how to reach, surrounding area)

## History & Significance
(historical background, cultural or functional importance)
