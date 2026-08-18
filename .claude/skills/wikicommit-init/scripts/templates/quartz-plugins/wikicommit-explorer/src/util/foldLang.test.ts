import { describe, expect, it } from "vitest"
import { detectCurrentLang, foldCurrentLangSegment, type FoldableNode } from "./foldLang"

function file(slugSegment: string): FoldableNode {
  return { slugSegment, isFolder: false, children: [] }
}

function folder(slugSegment: string | undefined, children: FoldableNode[]): FoldableNode {
  return { slugSegment, isFolder: true, children }
}

describe("detectCurrentLang", () => {
  it("returns the first segment when it looks like a 2-letter lang code", () => {
    expect(detectCurrentLang("ja/Person/yamada-taro")).toBe("ja")
    expect(detectCurrentLang("en/Organization/companya")).toBe("en")
  })

  it("returns null for non-lang first segments", () => {
    expect(detectCurrentLang("assets/logo.png")).toBeNull()
    expect(detectCurrentLang("index")).toBeNull()
    expect(detectCurrentLang("tags/engineer")).toBeNull()
    expect(detectCurrentLang("404")).toBeNull()
  })

  it("returns null for an empty slug", () => {
    expect(detectCurrentLang("")).toBeNull()
  })
})

describe("foldCurrentLangSegment", () => {
  it("promotes the current-language folder's children up to root", () => {
    const jaFolder = folder("ja", [folder("Person", [file("yamada-taro")]), folder("Organization", [])])
    const enFolder = folder("en", [folder("Person", [file("yamada-taro")])])
    const root = folder(undefined, [jaFolder, enFolder])

    foldCurrentLangSegment(root, "ja/Person/yamada-taro")

    expect(root.children).toEqual([folder("Person", [file("yamada-taro")]), folder("Organization", []), enFolder])
  })

  it("leaves sibling-language folders nested (not folded)", () => {
    const jaFolder = folder("ja", [folder("Person", [])])
    const enFolder = folder("en", [folder("Person", []), folder("Organization", [])])
    const root = folder(undefined, [jaFolder, enFolder])

    foldCurrentLangSegment(root, "ja/Person/yamada-taro")

    const enSibling = root.children.find((c) => c.slugSegment === "en")
    expect(enSibling).toBe(enFolder)
    expect(enSibling?.children).toHaveLength(2)
  })

  it("does not touch descendant node fields (slug-affecting data untouched)", () => {
    const personFolder = folder("Person", [file("yamada-taro")])
    const jaFolder = folder("ja", [personFolder])
    const root = folder(undefined, [jaFolder])

    foldCurrentLangSegment(root, "ja/Person/yamada-taro")

    expect(root.children[0]).toBe(personFolder)
  })

  it("folds the sole language folder on the root index page (single-language site)", () => {
    const personFolder = folder("Person", [])
    const jaFolder = folder("ja", [personFolder])
    const assetsFolder = folder("assets", [])
    const root = folder(undefined, [assetsFolder, jaFolder])

    foldCurrentLangSegment(root, "index")

    expect(root.children).toEqual([assetsFolder, personFolder])
  })

  it("is a no-op on the root index page when 2+ language folders exist (visitor must still choose)", () => {
    const jaFolder = folder("ja", [folder("Person", [])])
    const enFolder = folder("en", [folder("Person", [])])
    const root = folder(undefined, [jaFolder, enFolder])

    foldCurrentLangSegment(root, "index")

    expect(root.children).toEqual([jaFolder, enFolder])
  })

  it("is a no-op when currentSlug has no lang segment and no lang folder exists", () => {
    const assetsFolder = folder("assets", [])
    const root = folder(undefined, [assetsFolder])

    foldCurrentLangSegment(root, "index")

    expect(root.children).toEqual([assetsFolder])
  })

  it("is a no-op when no child folder matches the current language", () => {
    const enFolder = folder("en", [folder("Person", [])])
    const root = folder(undefined, [enFolder])

    foldCurrentLangSegment(root, "ja/Person/yamada-taro")

    expect(root.children).toEqual([enFolder])
  })

  it("re-sorts the merged root children when a sortFn is given", () => {
    const jaFolder = folder("ja", [folder("Zebra", []), folder("Apple", [])])
    const assetsFolder = folder("assets", [])
    const root = folder(undefined, [assetsFolder, jaFolder])

    const alphaSort = (a: FoldableNode, b: FoldableNode) =>
      (a.slugSegment ?? "").localeCompare(b.slugSegment ?? "")

    foldCurrentLangSegment(root, "ja/Zebra/index", alphaSort)

    expect(root.children.map((c) => c.slugSegment)).toEqual(["Apple", "assets", "Zebra"])
  })
})
