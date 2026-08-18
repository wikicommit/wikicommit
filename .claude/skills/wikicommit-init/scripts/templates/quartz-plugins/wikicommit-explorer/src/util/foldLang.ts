// New logic (not present upstream). .wikicommit/entity/<lang>/<Type>/<slug>.md is
// mirrored 1:1 into content/<lang>/<Type>/<slug>.md (see scripts/convert_wikilinks.py),
// so every Explorer tree has a <lang> folder ("ja", "en", ...) wrapping every
// Type directory. Without this, a reader has to expand that <lang> folder
// before any Type directory (Person, Organization, ...) becomes visible at
// all (Issue #209). WikiCommitLanguageSwitcher (a sibling component) already
// handles switching between languages, so Explorer's job here is narrower:
// only fold away the <lang> segment that matches the page currently being
// viewed, promoting its children up to root. Sibling-language folders (e.g.
// "en" while viewing a "ja" page) are left nested exactly as before, so they
// stay reachable by expanding them like any other folder.
//
// This only reorders where nodes sit in the tree — it does not touch
// node.slug (still includes the <lang> segment) or any other node field, so
// folder links, the localStorage collapse-state keys (keyed by node.slug),
// and every other node deeper in the tree are unaffected.
//
// Duplicated (not imported) in wikicommit-breadcrumbs and
// wikicommit-language-switcher — the 3 plugins are independent npm packages
// with no shared workspace, so there's no runtime-shareable module between
// them. tests/test_quartz_plugins_lang_segment_sync.py asserts this literal
// stays byte-identical across all 3 copies (Issue #228).
const LANG_SEGMENT_RE = /^[a-z]{2}$/

export interface FoldableNode {
  slugSegment?: string
  isFolder: boolean
  children: FoldableNode[]
}

/** First path segment of `slug`, if it looks like a 2-letter ISO 639-1 language code. */
export function detectCurrentLang(slug: string): string | null {
  const first = slug.split("/")[0] ?? ""
  return LANG_SEGMENT_RE.test(first) ? first : null
}

/**
 * Index of the sole language-code folder among `children`, or -1 if there
 * are zero or 2+ such folders. Used as a fallback for pages with no lang
 * segment in their slug (chiefly the root index page, slug "index"): with
 * exactly one language configured (the recommended `targets: []` setup —
 * see DesignDoc-data.md §3.3), that single folder should always be folded
 * so first-time visitors landing on the root page see the Type folders
 * directly instead of one extra click into a redundant lang folder (Issue
 * #246). With 2+ language folders this must stay -1: the visitor still has
 * to pick a language, so folding one arbitrarily would hide the others.
 */
function soleLangFolderIndex(children: FoldableNode[]): number {
  const matches: number[] = []
  children.forEach((child, index) => {
    if (child.isFolder && child.slugSegment !== undefined && LANG_SEGMENT_RE.test(child.slugSegment)) {
      matches.push(index)
    }
  })
  if (matches.length !== 1) return -1
  return matches[0] ?? -1
}

/**
 * Mutates `root.children` in place: if one of root's direct children is a
 * folder whose slugSegment matches the language of `currentSlug`, that
 * child is removed and its own children are spliced into `root.children`
 * at the same position. When `currentSlug` has no lang segment (e.g. the
 * root index page), falls back to folding the sole language folder when
 * exactly one exists (single-language site) — a no-op otherwise (multiple
 * language folders, or a page outside the <lang>/ layout with no lang
 * folders at all).
 */
export function foldCurrentLangSegment(
  root: FoldableNode,
  currentSlug: string,
  sortFn?: (a: FoldableNode, b: FoldableNode) => number,
): void {
  const currentLang = detectCurrentLang(currentSlug)
  const langNodeIndex = currentLang
    ? root.children.findIndex((child) => child.isFolder && child.slugSegment === currentLang)
    : soleLangFolderIndex(root.children)
  if (langNodeIndex === -1) return

  const langNode = root.children[langNodeIndex]
  if (!langNode) return
  root.children.splice(langNodeIndex, 1, ...langNode.children)

  if (sortFn) {
    root.children.sort(sortFn)
  }
}
