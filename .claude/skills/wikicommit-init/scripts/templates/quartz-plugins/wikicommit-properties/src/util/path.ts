import {
  resolveRelative as utilResolveRelative,
  slugifyFilePath,
  splitAnchor,
} from "@quartz-community/utils/path"
import type { FilePath, FullSlug } from "@quartz-community/types"

// Wraps @quartz-community/utils/path's resolveRelative(), which is typed
// against the branded FullSlug/SimpleSlug types. Frontmatter values here are
// plain strings extracted by regex (WikiLink/Markdown-link targets), not
// values that ever went through Quartz's own slug-branding pipeline, so a
// loosely-typed string -> string wrapper (matching upstream's own local
// resolveRelative()) avoids sprinkling `as FullSlug` casts through the
// component for values that were never validated as slugs to begin with.
export function resolveRelative(current: string, target: string): string {
  return utilResolveRelative(current as FullSlug, target as FullSlug)
}

/**
 * Convert a wikilink target like "My Note#Section" into the canonical slug
 * form "My-Note#section" so links rendered from frontmatter match the slugs
 * CrawlLinks produces for body links. Keeps the anchor after `#` intact.
 */
export function slugifyWikilinkTarget(target: string): string {
  const [rawPath, anchor] = splitAnchor(target)
  if (!rawPath) return anchor
  const pathWithExt = rawPath.endsWith(".md") ? rawPath : `${rawPath}.md`
  const slug = slugifyFilePath(pathWithExt as FilePath)
  return slug + anchor
}
