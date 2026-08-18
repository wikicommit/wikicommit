// Subpath import (matches transformer.ts/util/path.ts elsewhere in this
// plugin), not the bare "@quartz-community/utils" barrel — the barrel
// re-exports its jsx.ts/dom.ts submodules too, which pull in
// hast-util-to-jsx-runtime, a package this plugin never installed and
// doesn't otherwise need (verified: the bare import fails to bundle here).
import { getFullSlug } from "@quartz-community/utils/path"

// Page-scoped, not a single shared key (Issue #514, upstream-inherited bug
// #1): a shared key meant manually toggling the panel on one page would
// override every other page's own `quartz-properties-collapse` frontmatter
// setting the next time init() ran after SPA navigation, since this script
// always applied the last-saved global value unconditionally on top of the
// server-rendered initial state. Scoping by page identity means each page
// remembers its own manual toggle independently and a page with no prior
// interaction keeps showing its frontmatter-derived initial state
// (`details.open`, set server-side) untouched.
//
// Uses getFullSlug(window) (Quartz core's own client-side page-identity
// primitive — `window.document.body.dataset.slug`, set server-side on
// every page) rather than raw `window.location.pathname`: the slug is
// stable across base-path prefixes and the trailing-slash/index-page
// conventions that make two navigations to "the same" page produce two
// different `pathname` strings, which would otherwise reproduce this same
// class of bug (state that should be shared for one logical page silently
// isn't) at a narrower, URL-variant granularity.
const STORAGE_KEY_PREFIX = "wikicommit-properties-collapsed:"

function storageKey(): string {
  return STORAGE_KEY_PREFIX + getFullSlug(window)
}

function init() {
  const details = document.querySelector<HTMLDetailsElement>("details.wikicommit-properties")
  if (!details) return

  const key = storageKey()
  const saved = localStorage.getItem(key)
  if (saved !== null) {
    const isCollapsed = saved === "true"
    details.open = !isCollapsed
  }

  const toggleHandler = () => {
    localStorage.setItem(key, String(!details.open))
  }

  details.addEventListener("toggle", toggleHandler)

  if (typeof window !== "undefined" && window.addCleanup) {
    window.addCleanup(() => {
      details.removeEventListener("toggle", toggleHandler)
    })
  }
}

document.addEventListener("nav", () => {
  init()
})
document.addEventListener("render", () => {
  init()
})
