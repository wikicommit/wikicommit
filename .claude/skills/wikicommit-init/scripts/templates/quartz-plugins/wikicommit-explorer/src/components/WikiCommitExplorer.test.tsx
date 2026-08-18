import { describe, expect, it } from "vitest"
import WikiCommitExplorer, { explorerSortFn } from "./WikiCommitExplorer"

function folder(slugSegment: string, displayName?: string, slugSegments?: string[]) {
  return {
    slugSegment,
    slugSegments: slugSegments ?? [slugSegment],
    displayName: displayName ?? slugSegment,
    isFolder: true,
    data: null,
    children: [],
  }
}

function file(slugSegment: string, displayName?: string) {
  return { slugSegment, displayName: displayName ?? slugSegment, isFolder: false, data: {}, children: [] }
}

describe("explorerSortFn", () => {
  it("sorts non-language folders alphabetically, case-insensitive", () => {
    const nodes = [folder("Organization"), folder("DefinedTerm"), folder("HowTo")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["DefinedTerm", "HowTo", "Organization"])
  })

  it("sorts a sibling-language folder (e.g. en) after Type folders (Issue #334)", () => {
    const nodes = [folder("HowTo"), folder("en"), folder("DefinedTerm"), folder("Organization")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["DefinedTerm", "HowTo", "Organization", "en"])
  })

  it("sorts multiple language folders after Type folders, alphabetically among themselves", () => {
    const nodes = [folder("zh"), folder("HowTo"), folder("en"), folder("DefinedTerm")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["DefinedTerm", "HowTo", "en", "zh"])
  })

  it("does not treat a Type-cased 2-letter folder as a language folder", () => {
    // LANG_SEGMENT_RE only matches lowercase — WikiCommit's Type/custom-type naming
    // convention (PascalCase, docs/DesignDoc-data.md §5.3) never collides with it in
    // practice, but this pins the case-sensitivity as intentional.
    const nodes = [folder("en"), folder("Ab")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["Ab", "en"])
  })

  it("still sorts folders before files, and keeps language folders after files too", () => {
    const nodes = [file("readme"), folder("en"), folder("HowTo")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["HowTo", "readme", "en"])
  })

  it("sorts a root-level sources folder after language folders, always last (Issue #494)", () => {
    const nodes = [folder("sources"), folder("HowTo"), folder("en"), folder("DefinedTerm"), folder("zh")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["DefinedTerm", "HowTo", "en", "zh", "sources"])
  })

  it("keeps the root-level sources folder last even alongside files", () => {
    const nodes = [file("readme"), folder("sources"), folder("en")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["readme", "en", "sources"])
  })

  it("does not apply the sources tier to a folder named sources nested below the root", () => {
    // A folder named "sources" that isn't content/sources/ itself (e.g. nested under a Type
    // folder) must sort as an ordinary tier-0 entry, not get swept to the bottom.
    const nested = folder("sources", "sources", ["HowTo", "sources"])
    const nodes = [folder("zz-topic"), nested, folder("en")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["sources", "zz-topic", "en"])
  })

  it("is self-contained when serialized via toString (required for browser reconstruction)", () => {
    // WikiCommitExplorer serializes this via `.toString()` into the data-data-fns DOM
    // attribute, and wikicommit-explorer.inline.ts reconstructs it with `new Function(...)`,
    // which has no access to this module's imports/closures — only the literal source text.
    const source = explorerSortFn.toString()
    const reconstructed = new Function("a", "b", "return (" + source + ")(a, b)") as (
      a: unknown,
      b: unknown,
    ) => number

    const nodes = [folder("sources"), folder("en"), folder("HowTo")]
    nodes.sort((a, b) => reconstructed(a, b))

    expect(nodes.map((n) => n.slugSegment)).toEqual(["HowTo", "en", "sources"])
  })
})

describe("WikiCommitExplorer", () => {
  it("creates a component with default options", () => {
    const component = WikiCommitExplorer({})

    expect(component).toBeDefined()
    expect(typeof component).toBe("function")
  })

  it("creates a component with custom options", () => {
    const component = WikiCommitExplorer({
      title: "Custom Explorer",
      folderDefaultState: "open",
      folderClickBehavior: "collapse",
      useSavedState: false,
    })

    expect(component).toBeDefined()
    expect(typeof component).toBe("function")
  })

  it("exports a css string", () => {
    const component = WikiCommitExplorer({})

    expect(typeof component.css).toBe("string")
  })

  it("exports an afterDOMLoaded script (mocked in tests, see vitest.config.ts alias)", () => {
    const component = WikiCommitExplorer({})

    expect(typeof component.afterDOMLoaded).toBe("string")
    expect(component.afterDOMLoaded).toContain("mocked script")
  })
})
