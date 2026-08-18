import { describe, expect, it } from "vitest"
import { coerceToBool, getVisibleProperties } from "./transformer"
import type { WikiCommitPropertiesOptions } from "./types"

const baseOpts: WikiCommitPropertiesOptions = {
  includeAll: false,
  includedProperties: ["description", "tags", "aliases", "properties"],
  excludedProperties: [],
  hidePropertiesView: false,
  delimiters: "---",
  language: "yaml",
}

describe("getVisibleProperties (Issue #509 flattening)", () => {
  it("flattens WikiCommit's nested properties: block into individual top-level rows", () => {
    const data = {
      title: "山田太郎",
      tags: ["engineer"],
      properties: {
        description: "CompanyA のシニアエンジニア",
        affiliation: "[[Organization/companya]]",
        jobTitle: "シニアエンジニア",
      },
    }
    const result = getVisibleProperties(data, baseOpts)
    expect(result).toEqual({
      tags: ["engineer"],
      description: "CompanyA のシニアエンジニア",
      affiliation: "[[Organization/companya]]",
      jobTitle: "シニアエンジニア",
    })
    // The properties: key itself must not survive as a row (only its
    // flattened members do) — otherwise the raw JSON dump upstream renders
    // for object values would still show up next to the flattened rows.
    expect(result).not.toHaveProperty("properties")
  })

  it("preserves array values inside properties: (e.g. multiple WikiLinks) without flattening them further", () => {
    const data = {
      properties: {
        derivedFrom: ["[[Person/a]]", "[[Person/b]]"],
      },
    }
    const result = getVisibleProperties(data, baseOpts)
    expect(result.derivedFrom).toEqual(["[[Person/a]]", "[[Person/b]]"])
  })

  it("renders a page with no properties: block exactly as upstream did (no flattening applied)", () => {
    const data = { title: "x", tags: ["a"], aliases: ["y"] }
    const result = getVisibleProperties(data, baseOpts)
    expect(result).toEqual({ tags: ["a"], aliases: ["y"] })
  })

  it("omits properties: entirely when it is absent from includedProperties", () => {
    const optsWithoutProperties: WikiCommitPropertiesOptions = {
      ...baseOpts,
      includedProperties: ["description", "tags", "aliases"],
    }
    const data = { tags: ["a"], properties: { description: "should not appear" } }
    const result = getVisibleProperties(data, optsWithoutProperties)
    expect(result).toEqual({ tags: ["a"] })
  })

  it("applies excludedProperties to nested keys flattened out of properties:, not just top-level keys", () => {
    const opts: WikiCommitPropertiesOptions = { ...baseOpts, excludedProperties: ["jobTitle"] }
    const data = {
      properties: { description: "kept", jobTitle: "excluded" },
    }
    const result = getVisibleProperties(data, opts)
    expect(result).toEqual({ description: "kept" })
  })

  it("flattens any included object-valued property, not just one hardcoded to the name properties", () => {
    // getVisibleProperties() flattens by shape (plain object), not by key
    // name, so this also covers includeAll: true picking up an unrelated
    // object-valued frontmatter field.
    const opts: WikiCommitPropertiesOptions = { ...baseOpts, includeAll: true }
    const data = { customBlock: { foo: "bar" } }
    const result = getVisibleProperties(data, opts)
    expect(result).toEqual({ foo: "bar" })
  })

  it("still excludes Quartz-internal keys (quartz-properties etc.) from the result", () => {
    const data = {
      "quartz-properties": true,
      "quartz-properties-collapse": false,
      tags: ["a"],
    }
    const result = getVisibleProperties(data, { ...baseOpts, includeAll: true })
    expect(result).not.toHaveProperty("quartz-properties")
    expect(result).not.toHaveProperty("quartz-properties-collapse")
    expect(result.tags).toEqual(["a"])
  })

  it("does not flatten arrays, only plain objects", () => {
    const opts: WikiCommitPropertiesOptions = { ...baseOpts, includeAll: true }
    const data = { tags: ["a", "b"] }
    const result = getVisibleProperties(data, opts)
    expect(result.tags).toEqual(["a", "b"])
  })

  it("does not flatten null values", () => {
    const opts: WikiCommitPropertiesOptions = { ...baseOpts, includeAll: true }
    const data = { description: null }
    const result = getVisibleProperties(data, opts)
    expect(result.description).toBeNull()
  })

  // Custom types (docs/DesignDoc-data.md §5.3) are exempt from the
  // domainIncludes validation that keeps a standard type's properties:
  // disjoint from WikiCommit's own structural fields, so a custom type's
  // schema could declare a properties.tags that collides with the page's
  // real top-level tags. properties comes last in the default
  // includedProperties order, so without collision protection the nested
  // tags would silently clobber the real one.
  it("keeps the real top-level tags when a colliding properties.tags exists, instead of letting the flattened one win", () => {
    const data = {
      tags: ["dessert"],
      properties: { tags: ["[[Person/chef-a]]"] },
    }
    const result = getVisibleProperties(data, baseOpts)
    expect(result.tags).toEqual(["dessert"])
  })

  it("still keeps a colliding nested key when it is processed before the top-level field of the same name", () => {
    // Same collision, but with includedProperties reordered so properties
    // is selected first — first write should win regardless of which side
    // (top-level or nested) that turns out to be.
    const opts: WikiCommitPropertiesOptions = {
      ...baseOpts,
      includedProperties: ["properties", "tags"],
    }
    const data = {
      tags: ["dessert"],
      properties: { tags: ["[[Person/chef-a]]"] },
    }
    const result = getVisibleProperties(data, opts)
    expect(result.tags).toEqual(["[[Person/chef-a]]"])
  })
})

describe("coerceToBool (Issue #514, upstream-inherited bug #3)", () => {
  it("recognizes numeric 1/0 as true/false, not just string/boolean forms", () => {
    // `quartz-properties-collapse: 1` parses as a bare YAML number, not a
    // string — previously fell through every branch and returned undefined,
    // silently discarding the forced override.
    expect(coerceToBool(1)).toBe(true)
    expect(coerceToBool(0)).toBe(false)
  })

  it("still recognizes boolean and case-insensitive string forms", () => {
    expect(coerceToBool(true)).toBe(true)
    expect(coerceToBool(false)).toBe(false)
    expect(coerceToBool("true")).toBe(true)
    expect(coerceToBool("FALSE")).toBe(false)
  })

  it("returns undefined for a number other than 0/1, and for undefined/null/unrecognized strings", () => {
    expect(coerceToBool(2)).toBeUndefined()
    expect(coerceToBool(undefined)).toBeUndefined()
    expect(coerceToBool(null)).toBeUndefined()
    expect(coerceToBool("yes")).toBeUndefined()
  })
})
