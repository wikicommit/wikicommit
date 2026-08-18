import type { QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { describe, expect, it } from "vitest"
import WikiCommitBreadcrumbsConstructor from "./WikiCommitBreadcrumbs"

// Mirrors a small .wikicommit/entity/ tree, already mirrored into
// content/<lang>/<Type>/<slug>.md by scripts/convert_wikilinks.py (see the
// comment on translatedFromToRelativePath in WikiCommitSources.tsx for the
// same convention). `slug` here is already lowercased the way Quartz's
// build produces it, matching what trieFromAllFiles expects.
const allFiles = [
  {
    slug: "ja/person/yamada-taro",
    filePath: "content/ja/Person/yamada-taro.md",
    frontmatter: { title: "山田太郎" },
  },
  {
    slug: "ja/organization/companya",
    filePath: "content/ja/Organization/companya.md",
    frontmatter: { title: "CompanyA" },
  },
  {
    slug: "en/person/yamada-taro",
    filePath: "content/en/Person/yamada-taro.md",
    frontmatter: { title: "Taro Yamada" },
  },
]

type TestFile = {
  slug: string
  filePath?: string
  frontmatter: { title: string }
}

function renderBreadcrumbs(
  slug: string,
  opts: {
    showCurrentPage?: boolean
    ctx?: Record<string, unknown>
    files?: TestFile[]
  } = {},
): string | null {
  const Breadcrumbs = WikiCommitBreadcrumbsConstructor(
    opts.showCurrentPage === undefined ? undefined : { showCurrentPage: opts.showCurrentPage },
  )
  const props = {
    fileData: { slug },
    allFiles: opts.files ?? allFiles,
    displayClass: undefined,
    ctx: opts.ctx ?? {},
  } as unknown as QuartzComponentProps
  const result = Breadcrumbs(props)
  if (result === null) return null
  return render(result as VNode)
}

describe("WikiCommitBreadcrumbs", () => {
  it("is exported as a function that returns a component with a css property", () => {
    expect(typeof WikiCommitBreadcrumbsConstructor).toBe("function")
    const component = WikiCommitBreadcrumbsConstructor()
    expect(typeof component).toBe("function")
    expect(typeof component.css).toBe("string")
  })

  it("drops the lang segment from a regular content page's breadcrumb trail", () => {
    const html = renderBreadcrumbs("ja/person/yamada-taro")
    expect(html).toContain("Home")
    expect(html).toContain("Person")
    expect(html).toContain("山田太郎")
    // The "ja" lang segment must not appear as its own crumb anchor text.
    expect(html).not.toMatch(/<a href="[^"]*">ja<\/a>/)
  })

  it("still shows the Type folder crumb (only the lang segment is dropped)", () => {
    const html = renderBreadcrumbs("ja/organization/companya")
    expect(html).toContain("Organization")
    expect(html).toContain("CompanyA")
    expect(html).not.toMatch(/<a href="[^"]*">ja<\/a>/)
  })

  it("works the same for an en/ page (lang code is generic, not hardcoded to ja)", () => {
    const html = renderBreadcrumbs("en/person/yamada-taro")
    expect(html).toContain("Taro Yamada")
    expect(html).not.toMatch(/<a href="[^"]*">en<\/a>/)
  })

  it("renders just Home when browsing the lang-root folder page itself (showCurrentPage: true)", () => {
    const html = renderBreadcrumbs("ja/index")
    expect(html).toContain("Home")
    expect(html).not.toContain("ja")
  })

  it("does not collapse to an empty breadcrumb when showCurrentPage is false and the current page is the lang-root folder (pop-then-splice ordering regression)", () => {
    const html = renderBreadcrumbs("ja/index", { showCurrentPage: false })
    expect(html).not.toBeNull()
    expect(html).toContain("Home")
    expect(html?.match(/breadcrumb-element/g)?.length).toBe(1)
  })

  it("hides the current page's own crumb when showCurrentPage is false, independent of the lang-segment removal", () => {
    const html = renderBreadcrumbs("ja/person/yamada-taro", { showCurrentPage: false })
    expect(html).toContain("Home")
    expect(html).toContain("Person")
    expect(html).not.toContain("山田太郎")
  })

  it("returns null for a slug not present in the trie", () => {
    expect(renderBreadcrumbs("ja/person/nonexistent")).toBeNull()
  })

  it("caches the trie on ctx across renders instead of rebuilding it", () => {
    const ctx: Record<string, unknown> = {}
    renderBreadcrumbs("ja/person/yamada-taro", { ctx })
    expect(ctx.wikicommitBreadcrumbsTrie).toBeDefined()
    const trieAfterFirstRender = ctx.wikicommitBreadcrumbsTrie
    renderBreadcrumbs("ja/organization/companya", { ctx })
    expect(ctx.wikicommitBreadcrumbsTrie).toBe(trieAfterFirstRender)
  })

  // Regression test for Issue #210 item 1: Quartz core's PageTypeDispatcher
  // sets `ctx.trie` from its own non-virtual `allFiles` before any component
  // renders, and that core-built trie doesn't include tag-page/folder-page
  // virtual pages. If this component reused the shared `ctx.trie` key, the
  // `??=` would find core's value already set and skip building its own trie
  // from the (virtual-page-inclusive) `allFiles` prop, so a virtual page's
  // slug (e.g. a tag page under "tags/") would be missing from the trie and
  // ancestryChain() would return undefined, hiding the breadcrumb trail.
  it("still resolves breadcrumbs for a slug core's ctx.trie wouldn't know about (simulated tag/folder virtual page)", () => {
    const ctx: Record<string, unknown> = {
      // Simulates core's pre-built, non-virtual-only trie: it has no
      // knowledge of "tags/engineer" at all.
      trie: { ancestryChain: () => undefined },
    }
    const html = renderBreadcrumbs("ja/person/yamada-taro", { ctx })
    expect(html).toContain("山田太郎")
    // Confirms the component built (and used) its own trie rather than the
    // pre-seeded `ctx.trie` stand-in above, which would have returned null.
    expect(ctx.wikicommitBreadcrumbsTrie).toBeDefined()
  })

  // Regression test for Issue #236: Quartz's build generates virtual pages
  // (tag pages, folder pages) that have frontmatter but no on-disk filePath.
  // trieFromAllFiles() used to dereference file.filePath unconditionally via
  // fileTrie.ts's insert(), so these filePath-less entries crashed the build
  // with "Cannot read properties of undefined (reading 'split')" once Issue
  // #210's ctx-key fix made this component's own trieFromAllFiles() call
  // actually run against the virtual-page-inclusive `allFiles` prop.
  it("does not crash when allFiles contains a virtual page (frontmatter present, no filePath)", () => {
    const filesWithVirtualPage = [
      ...allFiles,
      { slug: "tags/engineer", frontmatter: { title: "engineer" } },
    ]
    let html: string | null = null
    // Regular pages still resolve fine alongside the virtual page.
    expect(() => {
      html = renderBreadcrumbs("ja/person/yamada-taro", { files: filesWithVirtualPage })
    }).not.toThrow()
    expect(html).toContain("山田太郎")
  })

  it("hides the breadcrumb trail (renders null) for a virtual page itself, rather than crashing", () => {
    const filesWithVirtualPage = [
      ...allFiles,
      { slug: "tags/engineer", frontmatter: { title: "engineer" } },
    ]
    expect(
      renderBreadcrumbs("tags/engineer", { files: filesWithVirtualPage }),
    ).toBeNull()
  })
})
