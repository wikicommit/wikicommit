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
    // convention (PascalCase) never collides with it in
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

  it("sorts a root-level overview folder before Type folders (Issue #946)", () => {
    const nodes = [folder("Organization"), folder("overview"), folder("DefinedTerm")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["overview", "DefinedTerm", "Organization"])
  })

  it("sorts overview before View, and both before Type folders (Issue #946)", () => {
    const nodes = [folder("Person"), folder("View"), folder("overview"), folder("DefinedTerm")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["overview", "View", "DefinedTerm", "Person"])
  })

  it("does not depend on the overview folder's display name, which is localized", () => {
    // The whole point of matching on the slug segment: the overview page's title comes from
    // OVERVIEW_LABELS, so an en wiki reads "Overview" and a ja one reads something starting
    // at W. Under display-name ordering those land in two different places (Issue #946).
    const en = [folder("Person"), folder("overview", "Overview"), folder("DefinedTerm")]
    const ja = [folder("Person"), folder("overview", "Wiki 全体の俯瞰"), folder("DefinedTerm")]

    en.sort(explorerSortFn)
    ja.sort(explorerSortFn)

    expect(en.map((n) => n.slugSegment)).toEqual(ja.map((n) => n.slugSegment))
    expect(en.map((n) => n.slugSegment)).toEqual(["overview", "DefinedTerm", "Person"])
  })

  it("leads a sibling language's Type folders with its View, which is not at the root", () => {
    // View gets no depth guard, unlike overview and sources: foldLang.ts leaves node.slug
    // alone when it lifts the current language to the root, so even a folded View still has
    // slugSegments of length 2. Applying the tier at any depth is what makes both cases work.
    const nested = folder("View", "View", ["en", "View"])
    const nodes = [folder("Person", "Person", ["en", "Person"]), nested]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["View", "Person"])
  })

  it("puts overview and sources at opposite ends of the root listing (Issue #946)", () => {
    const nodes = [
      folder("sources"),
      folder("Person"),
      folder("en"),
      folder("View"),
      folder("DefinedTerm"),
      folder("overview"),
    ]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual([
      "overview",
      "View",
      "DefinedTerm",
      "Person",
      "en",
      "sources",
    ])
  })

  it("does not apply the overview tier to a folder named overview nested below the root", () => {
    const nested = folder("overview", "overview", ["HowTo", "overview"])
    const nodes = [folder("Aa"), nested, folder("zz-topic")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["Aa", "overview", "zz-topic"])
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
