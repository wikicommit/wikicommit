// New logic (not present upstream). Issue #1035: a wiki can sort the pages of a
// large Type into groups (.wikicommit/groups/<Type>.yml) without rewriting any
// page. convert_wikilinks.py publishes the membership as wikicommit-groups.json
// next to contentIndex.json, because the content index carries no custom
// frontmatter; this module turns that manifest into a tree position.
//
// Only the position in the tree changes. The node's data (and so the link's
// href, built from data.slug) is the page's real slug — a grouped page keeps its
// URL, and regrouping never breaks a link from outside.

/** Prefix of a virtual group folder's slug segment. `#` never survives Quartz's
 * slugify (it is stripped), so no real page or folder can carry this segment. */
export const GROUP_SEGMENT_PREFIX = "#group-"

export interface GroupFolder {
  /** group key -> label, already resolved for this folder's language */
  groups: Record<string, string>
  /** published page slug segment -> group key */
  pages: Record<string, string>
}

export interface GroupManifest {
  version: number
  folders: Record<string, GroupFolder>
}

export interface GroupedPlacement {
  /** Trie path to insert at: the folder segments, the virtual segment, the page. */
  path: string[]
  /** filePath parts spliced the same way, so FileTrieNode.insert()'s per-folder
   * display hint still reads the right segment at every depth. */
  hintParts: string[]
  label: string
}

/** Where a page goes in the Explorer, or null to leave it where its slug puts it. */
export function groupedPlacement(
  slug: string,
  filePath: string | undefined,
  manifest: GroupManifest | null | undefined,
): GroupedPlacement | null {
  if (!manifest || typeof manifest !== "object" || !manifest.folders) return null
  const segments = slug.split("/")
  if (segments.length < 2) return null
  const page = segments[segments.length - 1] ?? ""
  if (page === "index") return null
  const folderSegments = segments.slice(0, -1)
  const folder = manifest.folders[folderSegments.join("/")]
  const key = folder?.pages?.[page]
  if (!folder || !key) return null
  const label = folder.groups?.[key] || key
  const virtual = GROUP_SEGMENT_PREFIX + key
  const fileParts = (filePath || slug).split("/")
  const hintParts = [...fileParts.slice(0, -1), virtual, fileParts[fileParts.length - 1] ?? page]
  return { path: [...folderSegments, virtual, page], hintParts, label }
}

