import { describe, expect, it } from "vitest"
import { WikiCommitJsonLD } from "./index"

type PageData = { frontmatter?: Record<string, unknown> }
type ScriptVNode = { type: string; props: { type: string; dangerouslySetInnerHTML: { __html: string } } }

function jsonLdFor(frontmatter: Record<string, unknown>): Record<string, unknown> | null {
  const plugin = WikiCommitJsonLD()
  const [generateJsonLD] = plugin.externalResources!({} as never)!.additionalHead as [
    (pageData: PageData) => ScriptVNode | null,
  ]
  const vnode = generateJsonLD({ frontmatter })
  if (vnode === null) return null
  return JSON.parse(vnode.props.dangerouslySetInnerHTML.__html)
}

describe("WikiCommitJsonLD plugin loader compatibility (Issue #62)", () => {
  it("registers as a transformer via htmlPlugins (satisfies Quartz v5 category validation)", () => {
    const plugin = WikiCommitJsonLD()
    expect(plugin.name).toBe("WikiCommitJsonLD")
    expect(plugin.htmlPlugins!({} as never)).toEqual([])
  })

  it("injects the JSON-LD script via externalResources().additionalHead", () => {
    const plugin = WikiCommitJsonLD()
    const resources = plugin.externalResources!({} as never)
    expect(resources?.additionalHead).toHaveLength(1)
  })
})

describe("frontmatter -> JSON-LD mapping", () => {
  it("maps title/tags/type to name/keywords/@type, and properties.description to description (Issue #495)", () => {
    const jsonld = jsonLdFor({
      type: "schema:Person",
      title: "山田太郎",
      tags: ["engineer", "ml"],
      properties: { description: "CompanyA のシニアエンジニア" },
    })
    expect(jsonld).toMatchObject({
      "@context": "https://schema.org",
      "@type": "Person",
      name: "山田太郎",
      description: "CompanyA のシニアエンジニア",
      keywords: ["engineer", "ml"],
    })
  })

  it("omits description when properties: is absent (no top-level description fallback)", () => {
    const jsonld = jsonLdFor({ type: "schema:Person", title: "x", description: "top-level, not nested" })
    expect(jsonld).not.toHaveProperty("description")
  })

  it("converts wikidata QID to a sameAs Wikidata URL", () => {
    const jsonld = jsonLdFor({ type: "schema:Person", title: "x", wikidata: "wd:Q12345" })
    expect(jsonld?.sameAs).toEqual(["https://www.wikidata.org/wiki/Q12345"])
  })

  it("appends the wikidata sameAs URL to an existing sameAs list", () => {
    const jsonld = jsonLdFor({
      type: "schema:Person",
      title: "x",
      sameAs: ["https://orcid.org/0000-0001-2345-6789"],
      wikidata: "wd:Q12345",
    })
    expect(jsonld?.sameAs).toEqual([
      "https://orcid.org/0000-0001-2345-6789",
      "https://www.wikidata.org/wiki/Q12345",
    ])
  })

  it("maps Person-specific fields nested under properties: (Issue #495)", () => {
    const jsonld = jsonLdFor({
      type: "schema:Person",
      title: "山田太郎",
      properties: {
        jobTitle: "シニアエンジニア",
        birthDate: "1980-01-01",
        affiliation: "CompanyA",
      },
    })
    expect(jsonld).toMatchObject({
      jobTitle: "シニアエンジニア",
      birthDate: "1980-01-01",
      affiliation: "CompanyA",
    })
  })

  it("omits a WikiLink-formatted affiliation instead of emitting the raw [[...]] text", () => {
    const jsonld = jsonLdFor({
      type: "schema:Person",
      title: "山田太郎",
      properties: { affiliation: "[[Organization/companya]]" },
    })
    expect(jsonld).not.toHaveProperty("affiliation")
  })

  it("maps Event-specific fields nested under properties: (Issue #495)", () => {
    const jsonld = jsonLdFor({
      type: "schema:Event",
      title: "Project Alpha Kickoff",
      properties: {
        startDate: "2026-01-01",
        endDate: "2026-01-02",
        location: "Tokyo",
      },
    })
    expect(jsonld).toMatchObject({
      "@type": "Event",
      startDate: "2026-01-01",
      endDate: "2026-01-02",
      location: "Tokyo",
    })
  })

  it("maps any properties: key generically, regardless of type (Issue #513)", () => {
    // Replaces the old Person/Event-only decision blocks: any key under
    // `properties:` now passes through for any type, since
    // validate_frontmatter.py already machine-verifies (at merge time) that
    // every properties: key legitimately belongs to that page's type before
    // this plugin ever sees it (Issue #495's domainIncludes check) — this
    // plugin no longer needs its own per-type allowlist.
    const jsonld = jsonLdFor({
      type: "schema:Organization",
      title: "CompanyA",
      properties: { foundingDate: "2010-04-01", numberOfEmployees: 42 },
    })
    expect(jsonld).toMatchObject({
      "@type": "Organization",
      foundingDate: "2010-04-01",
      numberOfEmployees: 42,
    })
  })

  it("maps DefinedTerm-specific properties generically (Issue #513)", () => {
    const jsonld = jsonLdFor({
      type: "schema:DefinedTerm",
      title: "Context Engineering",
      properties: { termCode: "context-engineering", inDefinedTermSet: "AI Glossary" },
    })
    expect(jsonld).toMatchObject({
      "@type": "DefinedTerm",
      termCode: "context-engineering",
      inDefinedTermSet: "AI Glossary",
    })
  })

  it("omits a WikiLink-formatted property value for any type, not just Person's affiliation (Issue #513)", () => {
    const jsonld = jsonLdFor({
      type: "schema:Organization",
      title: "CompanyA",
      properties: { parentOrganization: "[[Organization/parent-co]]" },
    })
    expect(jsonld).not.toHaveProperty("parentOrganization")
  })

  it("does not let properties.keywords (e.g. ScholarlyArticle) clobber tags-derived keywords", () => {
    const jsonld = jsonLdFor({
      type: "schema:ScholarlyArticle",
      title: "A Paper",
      tags: ["llm", "agents"],
      properties: { keywords: ["reasoning", "benchmarks"] },
    })
    expect(jsonld?.keywords).toEqual(["llm", "agents"])
  })

  it("filters WikiLink-formatted entries out of an array-valued property", () => {
    const jsonld = jsonLdFor({
      type: "schema:BlogPosting",
      title: "A Post",
      properties: { author: ["[[Person/yamada-taro]]", "Jane Doe"] },
    })
    expect(jsonld?.author).toEqual(["Jane Doe"])
  })

  it("omits an already-empty array-valued property instead of emitting an empty list", () => {
    const jsonld = jsonLdFor({
      type: "schema:Book",
      title: "A Novel",
      properties: { character: [] },
    })
    expect(jsonld).not.toHaveProperty("character")
  })

  it("omits an array-valued property entirely when every entry is a WikiLink", () => {
    const jsonld = jsonLdFor({
      type: "schema:Book",
      title: "A Novel",
      properties: { character: ["[[Person/yamada-taro]]"] },
    })
    expect(jsonld).not.toHaveProperty("character")
  })

  it("tolerates a missing or malformed properties: block without throwing", () => {
    expect(jsonLdFor({ type: "schema:Person", title: "x" })).toMatchObject({ "@type": "Person" })
    expect(jsonLdFor({ type: "schema:Person", title: "x", properties: "not an object" })).toMatchObject({
      "@type": "Person",
    })
  })

  it("returns null when type is missing", () => {
    expect(jsonLdFor({ title: "x" })).toBeNull()
  })

  it("returns null for a removed page", () => {
    expect(jsonLdFor({ type: "schema:Person", title: "x", status: "removed" })).toBeNull()
  })

  it("returns null for custom types with no Schema.org equivalent", () => {
    expect(jsonLdFor({ type: "schema:custom/Decision", title: "x" })).toBeNull()
  })

  it("escapes </script>-breakout sequences in the embedded JSON", () => {
    const plugin = WikiCommitJsonLD()
    const [generateJsonLD] = plugin.externalResources!({} as never)!.additionalHead as [
      (pageData: PageData) => ScriptVNode,
    ]
    const vnode = generateJsonLD({
      frontmatter: { type: "schema:Person", title: "</script><script>alert(1)</script>" },
    })
    expect(vnode.props.dangerouslySetInnerHTML.__html).not.toContain("</script>")
    expect(JSON.parse(vnode.props.dangerouslySetInnerHTML.__html).name).toBe(
      "</script><script>alert(1)</script>",
    )
  })
})
