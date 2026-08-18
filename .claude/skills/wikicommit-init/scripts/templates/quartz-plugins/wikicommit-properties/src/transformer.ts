import matter from "gray-matter"
import remarkFrontmatter from "remark-frontmatter"
import yaml from "js-yaml"
import toml from "toml"
import type {
  QuartzTransformerPlugin,
  BuildCtx,
  QuartzPluginData,
  FullSlug,
  FilePath,
} from "@quartz-community/types"
// Import from the "/path" subpath (not the package root) to avoid pulling in
// the unrelated jsx.ts module, whose hast-util-to-jsx-runtime dependency is
// missing from @quartz-community/utils's own package.json (same issue
// WikiCommitSources.tsx works around the same way).
import {
  slugTag,
  slugifyFilePath,
  getFileExtension,
  transformLink,
} from "@quartz-community/utils/path"
import type { TransformOptions } from "@quartz-community/utils/path"
import { slugifyWikilinkTarget } from "./util/path"
import type { WikiCommitPropertiesOptions } from "./types"

const defaultOptions: WikiCommitPropertiesOptions = {
  includeAll: false,
  // "properties" added to the upstream default (Issue #509) — this is the
  // nested Schema.org property block WikiCommit's own frontmatter design
  // adds (docs/DesignDoc-data.md §4.1, Issue #495). See getVisibleProperties()
  // below for how a nested-object value like this one gets flattened.
  includedProperties: ["description", "tags", "aliases", "properties"],
  excludedProperties: [],
  hidePropertiesView: false,
  delimiters: "---",
  language: "yaml",
}

function coalesceAliases(data: Record<string, unknown>, aliases: string[]): unknown | undefined {
  for (const alias of aliases) {
    if (data[alias] !== undefined && data[alias] !== null) return data[alias]
  }
}

function coerceToArray(input: unknown): string[] | undefined {
  if (input === undefined || input === null) return undefined

  if (!Array.isArray(input)) {
    return String(input)
      .split(",")
      .map((s: string) => s.trim())
  }

  return input
    .filter((v: unknown) => typeof v === "string" || typeof v === "number")
    .map((v: string | number) => v.toString())
}

function getAliasSlugs(aliases: string[]): FullSlug[] {
  return aliases.map((alias) => {
    const isMd = getFileExtension(alias) === ".md"
    const mockFp = isMd ? alias : alias + ".md"
    return slugifyFilePath(mockFp as FilePath)
  })
}

const WIKILINK_PATTERN = /\[\[([^\]|]+)(?:\|[^\]]+)?\]\]/g
const MDLINK_PATTERN = /\[(?:[^\]]*)\]\(([^)]+)\)/g

function extractLinksFromValue(value: unknown): string[] {
  if (typeof value === "string") {
    const links: string[] = []
    let match: RegExpExecArray | null

    WIKILINK_PATTERN.lastIndex = 0
    while ((match = WIKILINK_PATTERN.exec(value)) !== null) {
      links.push(slugifyWikilinkTarget(match[1]!))
    }

    MDLINK_PATTERN.lastIndex = 0
    while ((match = MDLINK_PATTERN.exec(value)) !== null) {
      links.push(match[1]!)
    }

    return links
  }

  if (Array.isArray(value)) {
    return value.flatMap((item) => extractLinksFromValue(item))
  }

  if (value !== null && typeof value === "object") {
    return Object.values(value).flatMap((v) => extractLinksFromValue(v))
  }

  return []
}

function collectLinkTargetsFromValue(value: unknown): Set<string> {
  const targets = new Set<string>()
  if (typeof value === "string") {
    let match: RegExpExecArray | null
    WIKILINK_PATTERN.lastIndex = 0
    while ((match = WIKILINK_PATTERN.exec(value)) !== null) {
      targets.add(slugifyWikilinkTarget(match[1]!))
    }
    MDLINK_PATTERN.lastIndex = 0
    while ((match = MDLINK_PATTERN.exec(value)) !== null) {
      targets.add(match[1]!)
    }
  } else if (Array.isArray(value)) {
    for (const item of value) {
      for (const t of collectLinkTargetsFromValue(item)) targets.add(t)
    }
  } else if (value !== null && typeof value === "object") {
    for (const v of Object.values(value)) {
      for (const t of collectLinkTargetsFromValue(v)) targets.add(t)
    }
  }
  return targets
}

/** Quartz-internal frontmatter keys that should never appear in the properties table. */
const QUARTZ_INTERNAL_KEYS = new Set([
  "quartz-properties",
  "quartzProperties",
  "quartz-properties-collapse",
  "quartzPropertiesCollapse",
])

// Exported (unlike upstream, which keeps this private) so transformer.test.ts
// can exercise it directly instead of driving the full gray-matter + remark
// markdownPlugins pipeline just to reach it — same rationale as
// getVisibleProperties() below (Issue #514).
export function coerceToBool(value: unknown): boolean | undefined {
  if (value === undefined || value === null) return undefined
  if (typeof value === "boolean") return value
  if (typeof value === "string") {
    const lower = value.toLowerCase()
    if (lower === "true") return true
    if (lower === "false") return false
  }
  // A bare `quartz-properties-collapse: 1`/`0` in YAML parses as a number,
  // not a string, so the string branch above never sees it and the override
  // was silently ignored (Issue #514, upstream-inherited bug #3).
  if (typeof value === "number") {
    if (value === 1) return true
    if (value === 0) return false
  }
  return undefined
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

// Exported (unlike upstream, which keeps this private) so build.test.ts can
// exercise the flattening logic directly instead of driving the full
// gray-matter + remark markdownPlugins pipeline just to reach it.
export function getVisibleProperties(
  data: Record<string, unknown>,
  opts: WikiCommitPropertiesOptions,
): Record<string, unknown> {
  const excluded = new Set(opts.excludedProperties)
  // Always exclude Quartz-internal keys from the visible properties table
  for (const key of QUARTZ_INTERNAL_KEYS) {
    excluded.add(key)
  }

  // New logic (not present upstream, Issue #509): WikiCommit nests all
  // Schema.org type-specific properties under a single `properties:` key
  // (docs/DesignDoc-data.md §4.1, Issue #495) rather than keeping them flat
  // at the frontmatter's top level. Upstream renders any object-valued
  // property as a single raw `JSON.stringify()` dump (see renderValue() in
  // WikiCommitProperties.tsx, unchanged from upstream), which would show
  // `properties:` as one unreadable JSON blob instead of the readable rows
  // every other top-level frontmatter field gets. Flattening one level here
  // — before rendering, not by changing renderValue() — makes each nested
  // key (e.g. `description`, `affiliation`) its own row, indistinguishable
  // from a top-level field, and reuses renderValue()'s existing
  // string/array/WikiLink handling for each flattened value as-is.
  // Only one level is flattened: WikiCommit's schema design keeps
  // `properties:` values scalar/array/WikiLink-string, never a further
  // nested object, so deeper nesting is not expected here.
  //
  // Selection and flattening happen in a single pass over the same key
  // order opts.includedProperties (or, in includeAll mode, Object.entries)
  // already establishes, and a key already written to `result` is never
  // overwritten — first write wins, regardless of whether it came from a
  // top-level field or a later-processed nested one. Without this guard, a
  // custom type (exempt from the domainIncludes checks that keep standard
  // types' `properties:` disjoint from WikiCommit's own structural fields,
  // docs/DesignDoc-data.md §5.3) could declare a `properties.tags` that
  // silently clobbers the page's real top-level `tags` — since `tags` is
  // processed before `properties` in the default includedProperties order,
  // the guard keeps the real tags and drops the colliding nested one
  // instead of the reverse.
  const result: Record<string, unknown> = {}
  const flattenInto = (key: string, value: unknown) => {
    if (isPlainObject(value)) {
      for (const [nestedKey, nestedValue] of Object.entries(value)) {
        if (!excluded.has(nestedKey) && !(nestedKey in result)) {
          result[nestedKey] = nestedValue
        }
      }
    } else if (!(key in result)) {
      result[key] = value
    }
  }

  if (opts.includeAll) {
    for (const [key, value] of Object.entries(data)) {
      if (!excluded.has(key)) flattenInto(key, value)
    }
  } else {
    for (const key of opts.includedProperties) {
      if (!excluded.has(key) && data[key] !== undefined) flattenInto(key, data[key])
    }
  }
  return result
}

export const WikiCommitProperties: QuartzTransformerPlugin<Partial<WikiCommitPropertiesOptions>> = (
  userOpts,
) => {
  const opts = { ...defaultOptions, ...userOpts }
  return {
    name: "WikiCommitProperties",
    markdownPlugins(_ctx: BuildCtx) {
      const { allSlugs } = _ctx
      return [
        [remarkFrontmatter, ["yaml", "toml"]],
        () => {
          return (_, file) => {
            const fileData = Buffer.from(file.value as Uint8Array)
            const { data } = matter(fileData, {
              delimiters: opts.delimiters,
              language: opts.language,
              engines: {
                yaml: (s) => yaml.load(s, { schema: yaml.JSON_SCHEMA }) as object,
                toml: (s) => toml.parse(s) as object,
              },
            })

            if (data.title != null && data.title.toString() !== "") {
              data.title = data.title.toString()
            } else {
              data.title = file.stem ?? "Untitled"
            }

            const tags = coerceToArray(coalesceAliases(data, ["tags", "tag"]))
            if (tags) data.tags = [...new Set(tags.map((tag: string) => slugTag(tag)))]

            const aliases = coerceToArray(coalesceAliases(data, ["aliases", "alias"]))
            if (aliases) {
              data.aliases = aliases
              file.data.aliases = getAliasSlugs(aliases)
              allSlugs.push(...file.data.aliases)
            }

            if (data.permalink != null && data.permalink.toString() !== "") {
              data.permalink = data.permalink.toString() as FullSlug
              const fileAliases = (file.data.aliases as FullSlug[]) ?? []
              fileAliases.push(data.permalink)
              file.data.aliases = fileAliases
              allSlugs.push(data.permalink)
            }

            const cssclasses = coerceToArray(coalesceAliases(data, ["cssclasses", "cssclass"]))
            if (cssclasses) data.cssclasses = cssclasses

            const socialImage = coalesceAliases(data, ["socialImage", "image", "cover"])

            const created = coalesceAliases(data, ["created", "date"])
            if (created) data.created = created

            const modified = coalesceAliases(data, [
              "modified",
              "lastmod",
              "updated",
              "last-modified",
            ])
            if (modified) data.modified = modified
            data.modified ||= created

            const published = coalesceAliases(data, ["published", "publishDate", "date"])
            if (published) data.published = published

            if (socialImage) data.socialImage = socialImage

            const uniqueSlugs = [...new Set(allSlugs)]
            allSlugs.splice(0, allSlugs.length, ...uniqueSlugs)

            const frontmatterLinks = extractLinksFromValue(data)
            if (frontmatterLinks.length > 0) {
              const existingLinks = (file.data.frontmatterLinks as string[]) ?? []
              file.data.frontmatterLinks = [...existingLinks, ...frontmatterLinks]
            }

            // Read per-note overrides for properties view visibility and collapsed state
            const showProperties = coerceToBool(
              coalesceAliases(data, ["quartz-properties", "quartzProperties"]),
            )
            const collapseProperties = coerceToBool(
              coalesceAliases(data, ["quartz-properties-collapse", "quartzPropertiesCollapse"]),
            )
            const visibleProps = getVisibleProperties(data, opts)
            file.data.wikicommitProperties = {
              properties: visibleProps,
              hideView: opts.hidePropertiesView,
              showProperties,
              collapseProperties,
            }

            file.data.frontmatter = data as QuartzPluginData["frontmatter"]
          }
        },
      ]
    },
    htmlPlugins(ctx: BuildCtx) {
      return [
        () => {
          return (_tree: unknown, file: { data: Record<string, unknown> }) => {
            const wcProps = file.data.wikicommitProperties as
              | { properties: Record<string, unknown>; resolvedLinks?: Record<string, string> }
              | undefined
            if (!wcProps) return

            const fileSlug = file.data.slug as FullSlug
            const transformOptions: TransformOptions = {
              strategy: "shortest",
              allSlugs: ctx.allSlugs,
            }

            const targets = new Set<string>()
            for (const value of Object.values(wcProps.properties)) {
              for (const t of collectLinkTargetsFromValue(value)) targets.add(t)
            }

            if (targets.size === 0) return

            const resolved: Record<string, string> = {}
            for (const target of targets) {
              resolved[target] = transformLink(fileSlug, target, transformOptions)
            }
            wcProps.resolvedLinks = resolved
          }
        },
      ]
    },
  }
}

declare module "vfile" {
  interface DataMap {
    aliases: FullSlug[]
    frontmatterLinks: string[]
    wikicommitProperties: {
      properties: Record<string, unknown>
      hideView: boolean
      showProperties?: boolean
      collapseProperties?: boolean
      resolvedLinks?: Record<string, string>
    }
  }
}
