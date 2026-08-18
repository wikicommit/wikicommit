import type { GlobalConfiguration, QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { afterEach, describe, expect, it } from "vitest"
import WikiCommitSourcesConstructor from "./WikiCommitSources"

const WikiCommitSources = WikiCommitSourcesConstructor()

function makeProps(
  frontmatter: Record<string, unknown>,
  opts: {
    slug?: string
    allFiles?: Record<string, unknown>[]
    cfg?: Partial<GlobalConfiguration>
  } = {},
): QuartzComponentProps {
  return {
    fileData: { slug: opts.slug ?? "ja/person/yamada-taro", frontmatter },
    allFiles: opts.allFiles ?? [],
    cfg: opts.cfg,
  } as unknown as QuartzComponentProps
}

function renderSources(
  frontmatter: Record<string, unknown>,
  opts: {
    slug?: string
    allFiles?: Record<string, unknown>[]
    cfg?: Partial<GlobalConfiguration>
  } = {},
): string | null {
  const result = WikiCommitSources(makeProps(frontmatter, opts))
  if (result === null) return null
  return render(result as VNode)
}

describe("WikiCommitSources", () => {
  afterEach(() => {
    delete process.env.GITHUB_REPOSITORY
  })

  it("renders nothing when sources is absent", () => {
    expect(renderSources({ title: "山田太郎" })).toBeNull()
  })

  it("renders nothing when sources is an empty array", () => {
    expect(renderSources({ title: "山田太郎", sources: [] })).toBeNull()
  })

  it("renders a path source as a GitHub blob link when GITHUB_REPOSITORY is set", () => {
    process.env.GITHUB_REPOSITORY = "wikicommit-dev/wikicommit"
    const html = renderSources({
      sources: [{ type: "path", path: "raw/paper 2024.pdf", hash: "sha256:abc" }],
    })
    expect(html).toContain("https://github.com/wikicommit-dev/wikicommit/blob/main/raw/paper%202024.pdf")
    expect(html).toContain("raw/paper 2024.pdf")
  })

  it("renders a path source as plain text when GITHUB_REPOSITORY is unset", () => {
    const html = renderSources({
      sources: [{ type: "path", path: "raw/paper-2024.pdf", hash: "sha256:abc" }],
    })
    expect(html).toContain("wikicommit-sources__text")
    expect(html).toContain("raw/paper-2024.pdf")
    expect(html).not.toContain("<a")
  })

  it("renders url and wikicommit sources as external links", () => {
    const html = renderSources({
      sources: [
        { type: "url", url: "https://example.com/article", hash: "sha256:def" },
        { type: "wikicommit", url: "https://other-wiki.example/page", hash: "sha256:ghi" },
      ],
    })
    expect(html).toContain('href="https://example.com/article"')
    expect(html).toContain('href="https://other-wiki.example/page"')
    expect(html).toContain('target="_blank"')
  })

  it("renders manual sources with author and created_at, no link", () => {
    const html = renderSources({
      sources: [{ type: "manual", author: "Taro Yamada", created_at: "2026-06-21" }],
    })
    expect(html).toContain("Taro Yamada")
    expect(html).toContain("2026-06-21")
    expect(html).not.toContain("<a")
  })

  it("falls back to the locale's unknown label when manual author is missing", () => {
    const html = renderSources({ sources: [{ type: "manual", created_at: "2026-06-21" }] })
    expect(html).toContain("unknown")
  })

  it("formats a created_at that YAML parsed as a Date instead of a string", () => {
    const html = renderSources({
      sources: [{ type: "manual", author: "Taro Yamada", created_at: new Date("2026-06-21T00:00:00Z") }],
    })
    expect(html).toContain("2026-06-21")
    expect(html).not.toContain("GMT")
  })

  it("renders nothing for the page itself when status is removed", () => {
    expect(
      renderSources({
        status: "removed",
        sources: [{ type: "url", url: "https://example.com/article" }],
      }),
    ).toBeNull()
  })

  it("skips malformed entries (missing required field) without throwing", () => {
    const html = renderSources({
      sources: [{ type: "path" }, { type: "url", url: "https://example.com" }],
    })
    expect(html).toContain("https://example.com")
  })

  it("returns null when all entries are malformed or of an unrecognized type", () => {
    expect(renderSources({ sources: [{ type: "path" }, { type: "unknown" }] })).toBeNull()
  })

  // allFiles entries mirror real Quartz vfile data: `slug` is lowercased by
  // Quartz's build (e.g. "ja/person/yamada-taro") while `relativePath`
  // preserves the original Type-segment casing (e.g.
  // "ja/Person/yamada-taro.md"), which is what translated_from resolution
  // must match against (see the comment on translatedFromToRelativePath in
  // the component).
  it("inherits sources from the parent page when translated_from is set and sources is omitted", () => {
    const html = renderSources(
      { title: "Taro Yamada", translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md" },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: {
              title: "山田太郎",
              sources: [{ type: "url", url: "https://example.com/article", hash: "sha256:def" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/article")
    expect(html).toContain("wikicommit-sources__inherited")
    expect(html).toContain("山田太郎")
  })

  it("renders nothing when translated_from points to a page with no sources", () => {
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md" },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: { title: "山田太郎" },
          },
        ],
      },
    )
    expect(html).toBeNull()
  })

  it("renders nothing when translated_from points to a nonexistent page", () => {
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/Person/nonexistent.md" },
      { slug: "en/person/nonexistent", allFiles: [] },
    )
    expect(html).toBeNull()
  })

  it("renders nothing when translated_from points to a page marked status: removed", () => {
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md" },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: {
              title: "山田太郎",
              status: "removed",
              sources: [{ type: "url", url: "https://example.com/article" }],
            },
          },
        ],
      },
    )
    expect(html).toBeNull()
  })

  it("ignores a non-string translated_from instead of throwing", () => {
    expect(() =>
      renderSources({ translated_from: true } as unknown as Record<string, unknown>),
    ).not.toThrow()
    expect(renderSources({ translated_from: true } as unknown as Record<string, unknown>)).toBeNull()
  })

  it("skips a path source whose path is not a string instead of throwing", () => {
    process.env.GITHUB_REPOSITORY = "wikicommit-dev/wikicommit"
    expect(() =>
      renderSources({
        sources: [
          { type: "path", path: ["not", "a", "string"] },
          { type: "url", url: "https://example.com" },
        ],
      }),
    ).not.toThrow()
  })

  it("inherits sources when translated_from has a leading ./ prefix", () => {
    // validate_frontmatter.py only checks that translated_from resolves to a
    // real file (repo_root / translated_from), so a hand-authored Route B
    // page can pass CI with a "./"-prefixed or whitespace-padded variant of
    // the canonical .wikicommit/entity/ path (Issue #378).
    const html = renderSources(
      { translated_from: "./.wikicommit/entity/ja/Person/yamada-taro.md" },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: {
              title: "山田太郎",
              sources: [{ type: "url", url: "https://example.com/article" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/article")
    expect(html).toContain("wikicommit-sources__inherited")
  })

  it("inherits sources when translated_from has surrounding whitespace", () => {
    const html = renderSources(
      { translated_from: "  .wikicommit/entity/ja/Person/yamada-taro.md  " },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: {
              title: "山田太郎",
              sources: [{ type: "url", url: "https://example.com/article" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/article")
  })

  it("inherits sources when translated_from still uses the pre-Issue-#477 .wikicommit/wiki/ prefix", () => {
    // A translation page written before the .wikicommit/wiki/ -> entity/
    // rename keeps its old translated_from verbatim (no auto-migration,
    // docs/DesignDoc-data.md §4.3's coexistence precedent), so the parent
    // lookup must still resolve it.
    const html = renderSources(
      { translated_from: ".wikicommit/wiki/ja/Person/yamada-taro.md" },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: {
              title: "山田太郎",
              sources: [{ type: "url", url: "https://example.com/article" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/article")
    expect(html).toContain("wikicommit-sources__inherited")
  })

  it("prefers the page's own sources over translated_from inheritance", () => {
    const html = renderSources(
      {
        translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
        sources: [{ type: "url", url: "https://example.com/own-source" }],
      },
      {
        slug: "en/person/yamada-taro",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: { sources: [{ type: "url", url: "https://example.com/parent-source" }] },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/own-source")
    expect(html).not.toContain("https://example.com/parent-source")
    expect(html).not.toContain("wikicommit-sources__inherited")
  })

  // Issue #378: WikiCommitSources used to key its caption ("Sources"/"出典")
  // off cfg.locale (a site-wide setting) unconditionally, so a bilingual
  // wiki's en/ pages showed the Japanese caption whenever quartz.config.yaml's
  // locale was ja-JP, and vice versa. frontmatter.lang now takes priority.
  it("uses the ja-JP caption for a ja page even when cfg.locale is unset (defaults to en-US)", () => {
    const html = renderSources(
      { lang: "ja", sources: [{ type: "url", url: "https://example.com/article" }] },
    )
    expect(html).toContain("出典")
    expect(html).not.toContain(">Sources<")
  })

  it("uses the English caption for an en page even when cfg.locale is ja-JP", () => {
    const html = renderSources(
      { lang: "en", sources: [{ type: "url", url: "https://example.com/article" }] },
      { cfg: { locale: "ja-JP" } as unknown as GlobalConfiguration },
    )
    expect(html).toContain(">Sources<")
    expect(html).not.toContain("出典")
  })

  it("falls back to cfg.locale when frontmatter.lang is absent", () => {
    const html = renderSources(
      { sources: [{ type: "url", url: "https://example.com/article" }] },
      { cfg: { locale: "ja-JP" } as unknown as GlobalConfiguration },
    )
    expect(html).toContain("出典")
  })
})
