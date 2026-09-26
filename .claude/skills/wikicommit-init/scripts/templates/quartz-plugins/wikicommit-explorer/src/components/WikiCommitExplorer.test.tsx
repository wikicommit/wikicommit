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
    // LANG_SEGMENT_RE only matches lowercase, and this pins that case-sensitivity as
    // intentional. It does NOT mean a collision cannot happen: the comparison is
    // against the published slug, which Quartz lowercases (Issue #981), so a
    // two-letter custom type does collide — custom/Ab publishes as content/<lang>/Ab/
    // once the custom/ segment is flattened away (Issue #576) and arrives here as
    // "ab", which this regex matches and files under the language tier. Left alone:
    // Schema.org has no two-letter type and a wiki naming a custom type in two letters
    // is remote, while the only way to tell the two apart would be to look at
    // displayName (a language folder has no index.md so its displayName falls back to
    // the slug, a Type folder has a title) — the display-name dependency Issue #946
    // deliberately refused for overview. Recorded as a known limit rather than fixed.
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
    const nodes = [folder("Person"), folder("view", "View"), folder("overview"), folder("DefinedTerm")]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["overview", "view", "DefinedTerm", "Person"])
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

  it("matches the slug Quartz actually publishes for View, not the on-disk spelling", () => {
    // Straight from a live contentIndex.json (wikicommit/ai-driven-dev-wiki, 2026-09-21):
    //
    //   "en/view/index"                     filePath: "en/View/index.md"
    //   "en/blogposting/agent-definition-…" filePath: "en/BlogPosting/…"
    //
    // filePath keeps the case; slug does not. The trie is built from slug
    // (FileTrieNode.add -> insert(file.slug.split("/"))), so slugSegment is "view" in
    // the browser — and Issue #946's tier, written as "View", never fired once in
    // production. The other tests here construct nodes by hand, which is exactly how
    // the wrong spelling stayed green, so this one derives both nodes from the slugs
    // quoted above rather than from the on-disk spelling.
    const fromSlug = (slug: string, displayName: string) => {
      const segments = slug.split("/").slice(0, -1)
      return folder(segments[segments.length - 1] as string, displayName, segments)
    }
    const nodes = [
      fromSlug("en/blogposting/agent-definition-drift", "BlogPosting"),
      fromSlug("en/view/index", "View"),
    ]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.displayName)).toEqual(["View", "BlogPosting"])
  })

  it("leads a sibling language's Type folders with its View, which is not at the root", () => {
    // View gets no depth guard, unlike overview and sources: foldLang.ts leaves node.slug
    // alone when it lifts the current language to the root, so even a folded View still has
    // slugSegments of length 2. Applying the tier at any depth is what makes both cases work.
    const nested = folder("view", "View", ["en", "view"])
    const nodes = [folder("Person", "Person", ["en", "Person"]), nested]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual(["view", "Person"])
  })

  it("puts overview and sources at opposite ends of the root listing (Issue #946)", () => {
    const nodes = [
      folder("sources"),
      folder("Person"),
      folder("en"),
      folder("view", "View"),
      folder("DefinedTerm"),
      folder("overview"),
    ]

    nodes.sort(explorerSortFn)

    expect(nodes.map((n) => n.slugSegment)).toEqual([
      "overview",
      "view",
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
