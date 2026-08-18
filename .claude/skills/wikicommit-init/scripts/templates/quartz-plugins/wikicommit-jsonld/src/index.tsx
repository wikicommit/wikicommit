import type { QuartzTransformerPlugin } from "@quartz-community/types"

type Frontmatter = Record<string, unknown>

function generateJsonLD(pageData: { frontmatter?: Frontmatter }) {
  const frontmatter = pageData.frontmatter
  if (!frontmatter?.type) return null
  if (frontmatter.status === "removed") return null

  const typeStr = String(frontmatter.type).replace(/^schema:/, "")
  // custom/ types have no Schema.org equivalent; omit rather than emit invalid JSON-LD
  if (typeStr.includes("/")) return null

  // Type-specific Schema.org properties live nested under `properties:`
  // (Issue #495) — everything else this function reads (title, tags,
  // sameAs, wikidata, status) stays flat at the top level of frontmatter,
  // since those are WikiCommit-wide identifier/bookkeeping fields read the
  // same way regardless of `type:`, not part of the per-type property set.
  const properties: Frontmatter =
    frontmatter.properties && typeof frontmatter.properties === "object"
      ? (frontmatter.properties as Frontmatter)
      : {}

  const jsonld: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": typeStr,
  }

  if (frontmatter.title) jsonld.name = frontmatter.title
  if (frontmatter.tags) jsonld.keywords = frontmatter.tags

  // wikidata → sameAs conversion: "wd:Q12345" → "https://www.wikidata.org/wiki/Q12345"
  const sameAs: string[] = Array.isArray(frontmatter.sameAs)
    ? frontmatter.sameAs.filter((x): x is string => typeof x === "string")
    : []
  if (frontmatter.wikidata) {
    const qid = String(frontmatter.wikidata).replace(/^wd:/, "")
    sameAs.push(`https://www.wikidata.org/wiki/${qid}`)
  }
  if (sameAs.length > 0) jsonld.sameAs = sameAs

  // Generic properties: -> JSON-LD mapping (Issue #513), replacing the old
  // Person/Event-only decision blocks (including the former separate
  // `description` read above, now folded into this same loop). Every
  // Schema.org-typed page already has its `properties:` keys machine-
  // verified against that page's `type:` domainIncludes by
  // validate_frontmatter.py at merge time (Issue #495) — so by the time
  // this plugin runs at build time, any key present under `properties:` is
  // already known to legitimately belong to this page's type, and no
  // per-type allowlist is needed here to keep e.g. Event-only fields off a
  // Person page.
  const isWikiLink = (v: unknown): boolean => typeof v === "string" && v.startsWith("[[")
  // Keys already populated above from WikiCommit-wide top-level frontmatter
  // fields (title/tags/sameAs), not from `properties:`. At least one
  // Schema.org type template declares a `properties:` key with the same
  // name as one of these JSON-LD output keys (ScholarlyArticle's
  // `properties.keywords`, which is a legitimate domainIncludes-verified
  // CreativeWork.keywords value, collides with the `keywords` this
  // function already derives from `tags`) — without this guard the loop
  // below would silently clobber the tags-derived value.
  const reservedOutputKeys = new Set(["name", "keywords", "sameAs"])
  for (const [key, value] of Object.entries(properties)) {
    if (reservedOutputKeys.has(key)) continue
    if (value === undefined || value === null || value === "") continue
    // WikiLink-formatted values (e.g. affiliation: "[[Organization/companya]]")
    // reference another wiki page rather than a literal value; applied to
    // every property uniformly, not just the Person-only `affiliation`
    // check this replaces. Several properties (author, character, tool,
    // supply, ...) are declared as YAML lists, so the same check must also
    // be applied element-wise — otherwise a WikiLink-formatted list entry
    // (e.g. author: ["[[Person/yamada-taro]]"]) leaks raw `[[...]]` syntax
    // into the public JSON-LD.
    if (isWikiLink(value)) continue
    if (Array.isArray(value)) {
      const filtered = value.filter((v) => !isWikiLink(v))
      if (filtered.length === 0) continue
      jsonld[key] = filtered
      continue
    }
    jsonld[key] = value
  }

  // Escape </script> sequences to prevent script-tag breakout XSS in inline JSON-LD
  const jsonString = JSON.stringify(jsonld, null, 2)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")

  // JSX (not a direct h() call) so tsup/esbuild's automatic JSX runtime
  // inlines the vnode-creation helper, keeping dist/index.js free of a
  // bare `import ... from "preact"` that this standalone plugin directory
  // (outside any node_modules tree) cannot resolve at runtime (Issue #186).
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: jsonString }}
    />
  )
}

export const WikiCommitJsonLD: QuartzTransformerPlugin = () => {
  return {
    name: "WikiCommitJsonLD",
    // No-op: Quartz's transformer category validation (config-loader.ts validateCategory)
    // only recognizes textTransform/markdownPlugins/htmlPlugins as evidence of a transformer,
    // so a plugin that only implements externalResources gets skipped as invalid. This
    // satisfies that check without altering the HTML AST; the actual injection happens
    // via externalResources below (see Issue #62).
    htmlPlugins() {
      return []
    },
    externalResources() {
      return {
        // additionalHead accepts (pageData) => JSX.Element functions;
        // Head.tsx calls each function with per-page fileData at render time.
        additionalHead: [generateJsonLD as (pageData: unknown) => unknown],
      }
    },
  }
}

export default WikiCommitJsonLD
