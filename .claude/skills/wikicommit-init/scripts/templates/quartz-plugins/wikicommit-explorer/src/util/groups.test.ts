import { describe, expect, it } from "vitest"
import { GROUP_SEGMENT_PREFIX, groupedPlacement, type GroupManifest } from "./groups"

const manifest: GroupManifest = {
  version: 1,
  folders: {
    "en/definedterm": {
      groups: { practice: "Practices" },
      pages: { "vibe-coding": "practice", "no-label": "bare" },
    },
  },
}

describe("groupedPlacement", () => {
  it("files a grouped page under a virtual folder inside its Type folder", () => {
    const placement = groupedPlacement("en/definedterm/vibe-coding", "en/DefinedTerm/vibe-coding.md", manifest)
    expect(placement).toEqual({
      path: ["en", "definedterm", `${GROUP_SEGMENT_PREFIX}practice`, "vibe-coding"],
      hintParts: ["en", "DefinedTerm", `${GROUP_SEGMENT_PREFIX}practice`, "vibe-coding.md"],
      label: "Practices",
    })
  })

  it("keeps the trie path and the hint parts the same length", () => {
    const placement = groupedPlacement("en/definedterm/vibe-coding", "en/DefinedTerm/vibe-coding.md", manifest)
    expect(placement?.hintParts.length).toBe(placement?.path.length)
  })

  it("falls back to the group key when no label was published", () => {
    expect(groupedPlacement("en/definedterm/no-label", undefined, manifest)?.label).toBe("bare")
  })

  it("leaves an ungrouped page, an index and another folder where they are", () => {
    expect(groupedPlacement("en/definedterm/other", undefined, manifest)).toBeNull()
    expect(groupedPlacement("en/definedterm/index", undefined, manifest)).toBeNull()
    expect(groupedPlacement("ja/definedterm/vibe-coding", undefined, manifest)).toBeNull()
  })

  it("treats a missing or malformed manifest as no groups", () => {
    expect(groupedPlacement("en/definedterm/vibe-coding", undefined, null)).toBeNull()
    expect(groupedPlacement("en/definedterm/vibe-coding", undefined, {} as GroupManifest)).toBeNull()
  })

  it("uses a prefix no published slug segment can carry", () => {
    // Quartz's slugify strips `#`, so a real page or folder never collides.
    expect(GROUP_SEGMENT_PREFIX.startsWith("#")).toBe(true)
  })
})
