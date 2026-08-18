import type { QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { describe, expect, it } from "vitest"
import WikiCommitLanguageSwitcherConstructor from "./WikiCommitLanguageSwitcher"

const WikiCommitLanguageSwitcher = WikiCommitLanguageSwitcherConstructor()

function makeProps(
  frontmatter: Record<string, unknown>,
  opts: {
    slug?: string
    relativePath?: string
    allFiles?: Record<string, unknown>[]
    locale?: string
    ctx?: Record<string, unknown>
  } = {},
): QuartzComponentProps {
  return {
    fileData: {
      slug: opts.slug ?? "ja/person/yamada-taro",
      relativePath: opts.relativePath ?? "ja/Person/yamada-taro.md",
      frontmatter,
    },
    allFiles: opts.allFiles ?? [],
    cfg: { locale: opts.locale ?? "en-US" },
    ctx: opts.ctx,
  } as unknown as QuartzComponentProps
}

function renderSwitcher(
  frontmatter: Record<string, unknown>,
  opts: {
    slug?: string
    relativePath?: string
    allFiles?: Record<string, unknown>[]
    locale?: string
    ctx?: Record<string, unknown>
  } = {},
): string | null {
  const result = WikiCommitLanguageSwitcher(makeProps(frontmatter, opts))
  if (result === null) return null
  return render(result as VNode)
}

// allFiles entries mirror real Quartz vfile data: `slug` is lowercased by
// Quartz's build (e.g. "ja/person/yamada-taro") while `relativePath`
// preserves the original Type-segment casing (e.g.
// "ja/Person/yamada-taro.md"). Both this component and WikiCommitSources
// match siblings via relativePath for that reason.
const jaSelf = {
  slug: "ja/person/yamada-taro",
  relativePath: "ja/Person/yamada-taro.md",
  frontmatter: { title: "山田太郎" },
}
const enSibling = {
  slug: "en/person/yamada-taro",
  relativePath: "en/Person/yamada-taro.md",
  frontmatter: { title: "Taro Yamada", translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md" },
}

describe("WikiCommitLanguageSwitcher", () => {
  it("renders nothing when no other-language version exists", () => {
    expect(renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf] })).toBeNull()
  })

  it("renders nothing when allFiles is empty (self not even matched)", () => {
    expect(renderSwitcher(jaSelf.frontmatter)).toBeNull()
  })

  it("renders a link to the other-language sibling", () => {
    const html = renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, enSibling] })
    expect(html).not.toBeNull()
    expect(html).toContain("wikicommit-language-switcher")
    expect(html).toContain('href="../../en/person/yamada-taro"')
    expect(html).toContain("English")
  })

  it("marks the current language as non-link text, not an <a>", () => {
    const html = renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, enSibling] })
    expect(html).toContain('aria-current="true"')
    expect(html).toContain("日本語")
    // "日本語" (current) must not itself be wrapped in an <a>; only "English" is a link.
    expect(html?.match(/<a /g)?.length).toBe(1)
  })

  it("renders from the translation's point of view too, linking back to the original", () => {
    const html = renderSwitcher(enSibling.frontmatter, {
      slug: "en/person/yamada-taro",
      relativePath: "en/Person/yamada-taro.md",
      allFiles: [jaSelf, enSibling],
    })
    expect(html).toContain('href="../../ja/person/yamada-taro"')
    expect(html).toContain("日本語")
  })

  it("sorts language entries alphabetically by lang code", () => {
    const zhSibling = {
      slug: "zh/person/yamada-taro",
      relativePath: "zh/Person/yamada-taro.md",
      frontmatter: { title: "山田太郎", translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md" },
    }
    const html = renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, enSibling, zhSibling] })
    const enIndex = html?.indexOf("English") ?? -1
    const jaIndex = html?.indexOf("日本語") ?? -1
    const zhIndex = html?.indexOf("中文") ?? -1
    expect(enIndex).toBeGreaterThan(-1)
    expect(enIndex).toBeLessThan(jaIndex)
    expect(jaIndex).toBeLessThan(zhIndex)
  })

  it("falls back to the uppercased code for an unrecognized language", () => {
    const xxSibling = {
      slug: "xx/person/yamada-taro",
      relativePath: "xx/Person/yamada-taro.md",
      frontmatter: { title: "Yamada Taro" },
    }
    const html = renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, xxSibling] })
    expect(html).toContain("XX")
  })

  it("excludes a sibling marked status: removed", () => {
    const removedEn = {
      ...enSibling,
      frontmatter: { ...enSibling.frontmatter, status: "removed" },
    }
    expect(renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, removedEn] })).toBeNull()
  })

  it("renders nothing when the current page itself is status: removed", () => {
    expect(
      renderSwitcher(
        { ...jaSelf.frontmatter, status: "removed" },
        { allFiles: [{ ...jaSelf, frontmatter: { ...jaSelf.frontmatter, status: "removed" } }, enSibling] },
      ),
    ).toBeNull()
  })

  it("ignores files whose relativePath has no lang-like first segment (e.g. assets/)", () => {
    const asset = {
      slug: "assets/logo",
      relativePath: "assets/logo.png",
      frontmatter: { title: "logo" },
    }
    expect(renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, asset, enSibling] })).not.toBeNull()
    // The asset itself, rendered as the "current" page, should not blow up and should yield null
    // (its relativePath's first segment "assets" isn't a 2-letter lang code).
    expect(
      renderSwitcher(asset.frontmatter, {
        slug: "assets/logo",
        relativePath: "assets/logo.png",
        allFiles: [jaSelf, asset, enSibling],
      }),
    ).toBeNull()
  })

  it("ignores the generated root index.md (relativePath has no '/')", () => {
    expect(
      renderSwitcher(
        { title: "Home" },
        { slug: "index", relativePath: "index.md", allFiles: [jaSelf, enSibling] },
      ),
    ).toBeNull()
  })

  it("does not throw and returns null when relativePath is missing", () => {
    const props = {
      fileData: { slug: "ja/person/yamada-taro", frontmatter: jaSelf.frontmatter },
      allFiles: [enSibling],
      cfg: { locale: "en-US" },
    } as unknown as QuartzComponentProps
    expect(() => WikiCommitLanguageSwitcher(props)).not.toThrow()
    expect(WikiCommitLanguageSwitcher(props)).toBeNull()
  })

  it("caches the per-build language index on ctx across renders instead of rescanning allFiles", () => {
    const ctx: Record<string, unknown> = {}
    renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf, enSibling], ctx })
    expect(ctx.wikicommitLanguageIndex).toBeDefined()
    const indexAfterFirstRender = ctx.wikicommitLanguageIndex
    // A second render reusing the same ctx must reuse the same index instance,
    // even though the allFiles it's passed no longer includes the sibling —
    // proving the lookup came from the cached index, not a fresh scan.
    const html = renderSwitcher(jaSelf.frontmatter, { allFiles: [jaSelf], ctx })
    expect(ctx.wikicommitLanguageIndex).toBe(indexAfterFirstRender)
    expect(html).toContain("English")
  })
})
