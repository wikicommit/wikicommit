// Vendored from github:quartz-community/breadcrumbs (src/util/fileTrie.ts),
// which does not export this module publicly. Behavior is kept identical to
// the upstream source (only the import path below differs) so this fork
// only diverges in WikiCommitBreadcrumbs.tsx's crumb-building logic.
//
// Imported from the "/path" subpath rather than the package root: the root
// re-exports jsx.ts too, which depends on hast-util-to-jsx-runtime — a
// dependency @quartz-community/utils declares as an optional peerDependency
// that isn't installed here (same issue documented on the resolveRelative
// import in WikiCommitSources.tsx of the wikicommit-sources plugin).
import { joinSegments } from "@quartz-community/utils/path"

interface FileTrieData {
  slug: string
  title: string
  filePath: string
}

export class FileTrieNode<T extends FileTrieData = FileTrieData> {
  isFolder: boolean
  children: Array<FileTrieNode<T>>

  private slugSegments: string[]
  private fileSegmentHint?: string
  private displayNameOverride?: string
  data: T | null

  constructor(segments: string[], data?: T) {
    this.children = []
    this.slugSegments = segments
    this.data = data ?? null
    this.isFolder = false
    this.displayNameOverride = undefined
  }

  get displayName(): string {
    const nonIndexTitle = this.data?.title === "index" ? undefined : this.data?.title
    return (
      this.displayNameOverride ?? nonIndexTitle ?? this.fileSegmentHint ?? this.slugSegment ?? ""
    )
  }

  set displayName(name: string) {
    this.displayNameOverride = name
  }

  get slug(): string {
    const path = joinSegments(...this.slugSegments)
    if (this.isFolder) {
      return joinSegments(path, "index")
    }

    return path
  }

  get slugSegment(): string {
    return this.slugSegments[this.slugSegments.length - 1] ?? ""
  }

  private makeChild(path: string[], file?: T): FileTrieNode<T> {
    const nextSegment = path[0]
    if (!nextSegment) {
      throw new Error("path is empty")
    }
    const fullPath = [...this.slugSegments, nextSegment]
    const child = new FileTrieNode<T>(fullPath, file)
    this.children.push(child)
    return child
  }

  private insert(path: string[], file: T): void {
    if (path.length === 0) {
      throw new Error("path is empty")
    }

    this.isFolder = true
    const segment = path[0]
    if (!segment) {
      throw new Error("path is empty")
    }
    if (path.length === 1) {
      if (segment === "index") {
        this.data ??= file
      } else {
        this.makeChild(path, file)
      }
    } else if (path.length > 1) {
      const child =
        this.children.find((c) => c.slugSegment === segment) ?? this.makeChild(path, undefined)

      const fileParts = file.filePath.split("/")
      const hint = fileParts.at(-path.length)
      if (hint) {
        child.fileSegmentHint = hint
      }
      child.insert(path.slice(1), file)
    }
  }

  add(file: T): void {
    this.insert(file.slug.split("/"), file)
  }

  findNode(path: string[]): FileTrieNode<T> | undefined {
    if (path.length === 0 || (path.length === 1 && path[0] === "index")) {
      return this
    }

    return this.children.find((c) => c.slugSegment === path[0])?.findNode(path.slice(1))
  }

  ancestryChain(path: string[]): Array<FileTrieNode<T>> | undefined {
    if (path.length === 0 || (path.length === 1 && path[0] === "index")) {
      return [this]
    }

    const child = this.children.find((c) => c.slugSegment === path[0])
    if (!child) {
      return undefined
    }

    const childPath = child.ancestryChain(path.slice(1))
    if (!childPath) {
      return undefined
    }

    return [this, ...childPath]
  }

  filter(filterFn: (node: FileTrieNode<T>) => boolean): void {
    this.children = this.children.filter(filterFn)
    this.children.forEach((child) => child.filter(filterFn))
  }

  map(mapFn: (node: FileTrieNode<T>) => void): void {
    mapFn(this)
    this.children.forEach((child) => child.map(mapFn))
  }

  sort(sortFn: (a: FileTrieNode<T>, b: FileTrieNode<T>) => number): void {
    this.children = this.children.sort(sortFn)
    this.children.forEach((e) => e.sort(sortFn))
  }
}

export function trieFromAllFiles(
  allFiles: Array<{
    slug?: string
    filePath?: string
    frontmatter?: { title?: string; [key: string]: unknown }
  }>,
): FileTrieNode {
  const trie = new FileTrieNode([])
  allFiles.forEach((file) => {
    // Quartz's build generates virtual pages (tag pages, folder pages) that
    // carry frontmatter but have no on-disk filePath. insert() dereferences
    // file.filePath (fileTrie.ts's insert(), via fileParts.at(-path.length))
    // for any non-leaf path segment, so passing a virtual page through would
    // throw on the `undefined.split("/")` call. Skipping filePath-less files
    // here means virtual pages are absent from the trie, so their own
    // ancestryChain() lookup returns undefined and WikiCommitBreadcrumbs
    // renders null (no breadcrumb trail) for them instead of crashing the
    // build (Issue #236).
    //
    // This guard is broader than strictly necessary: insert() only ever
    // dereferences file.filePath in its path.length > 1 branch (the
    // `fileParts = file.filePath.split("/")` line above), so a
    // *single-segment* virtual page would never crash insert() even
    // without this guard, and excluding it here means only its own (self)
    // breadcrumb goes missing rather than staying visible. This was
    // flagged as a theoretical over-exclusion (Issue #267), but
    // investigating Quartz v4/v5's actual emitters (upstream
    // jackyzha0/quartz's quartz/plugins/emitters/tagPage.tsx and
    // folderPage.tsx, which WikiCommit's tag-page/folder-page setup uses
    // unmodified) shows it doesn't happen in practice: tagPage.tsx always
    // emits 2-segment slugs (tags/<tag>, tags/index), and folderPage.tsx
    // always emits joinSegments(folder, "index"), which is single-segment
    // ("index") only for the root folder — and that case already lands in
    // insert()'s `segment === "index"` branch, which sets `this.data`
    // directly and never touches filePath either, so it's unaffected by
    // where this guard sits. No other Quartz emitter contributes entries
    // to the `allFiles` this function receives (aliases.ts, the other
    // candidate, writes its redirect pages straight to disk without
    // touching the shared content list). So no known input actually
    // exercises the "single-segment, non-index virtual page" scenario
    // Issue #267 raised — moving the guard into insert() would change no
    // observable behavior, while reintroducing a (currently moot) risk of
    // silently changing the tag/folder page visibility behavior confirmed
    // under Issue #236 if Quartz's emitters ever grow a single-segment
    // virtual page in the future. Decision: keep the guard here, unchanged.
    if (file.frontmatter && file.filePath) {
      trie.add({
        slug: file.slug!,
        title: file.frontmatter.title ?? "",
        filePath: file.filePath,
      })
    }
  })

  return trie
}
