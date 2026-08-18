import type { GlobalConfiguration, QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { describe, expect, it } from "vitest"
import WikiCommitPropertiesConstructor from "./WikiCommitProperties"

const WikiCommitProperties = WikiCommitPropertiesConstructor()

interface WcProps {
  properties: Record<string, unknown>
  hideView?: boolean
  showProperties?: boolean
  collapseProperties?: boolean
  resolvedLinks?: Record<string, string>
}

function makeProps(
  wikicommitProperties: WcProps | undefined,
  opts: {
    slug?: string
    frontmatter?: Record<string, unknown>
    cfg?: Partial<GlobalConfiguration>
  } = {},
): QuartzComponentProps {
  return {
    fileData: {
      slug: opts.slug ?? "ja/person/yamada-taro",
      frontmatter: opts.frontmatter ?? {},
      wikicommitProperties,
    },
    cfg: opts.cfg,
  } as unknown as QuartzComponentProps
}

function renderProperties(
  wikicommitProperties: WcProps | undefined,
  opts: Parameters<typeof makeProps>[1] = {},
): string | null {
  const result = WikiCommitProperties(makeProps(wikicommitProperties, opts))
  if (result === null) return null
  return render(result as VNode)
}

describe("WikiCommitProperties", () => {
  it("renders nothing when wikicommitProperties data is absent (transformer did not run)", () => {
    expect(renderProperties(undefined)).toBeNull()
  })

  it("renders nothing when properties is empty", () => {
    expect(renderProperties({ properties: {} })).toBeNull()
  })

  it("renders each already-flattened property key (Issue #509) as its own row", () => {
    const html = renderProperties({
      properties: {
        description: "CompanyA のシニアエンジニア",
        jobTitle: "シニアエンジニア",
      },
    })
    expect(html).toContain("wikicommit-properties-key")
    expect(html).toContain(">description<")
    expect(html).toContain(">jobTitle<")
    expect(html).toContain("CompanyA のシニアエンジニア")
    expect(html).toContain("シニアエンジニア")
  })

  it("renders a WikiLink-formatted string value (e.g. a flattened properties.affiliation) as a clickable link", () => {
    const html = renderProperties({
      properties: { affiliation: "[[Organization/companya]]" },
      resolvedLinks: { "organization/companya": "../../organization/companya" },
    })
    expect(html).toContain('href="../../organization/companya"')
    expect(html).toContain(">Organization/companya</a>")
  })

  it("falls back to resolveRelative when a WikiLink target is not in resolvedLinks", () => {
    const html = renderProperties({
      properties: { affiliation: "[[Organization/companya]]" },
    })
    expect(html).toContain("<a")
    // slug is "ja/person/yamada-taro" (2 segments deep) -> "../../" to root
    expect(html).toContain('href="../../organization/companya"')
  })

  it("renders array values comma-separated", () => {
    const html = renderProperties({
      properties: { derivedFrom: ["[[Person/a]]", "[[Person/b]]"] },
    })
    expect(html).toContain("wikicommit-properties-list")
    expect(html).toContain("wikicommit-properties-separator")
  })

  it("renders the tags key as tag links, not plain WikiLink text", () => {
    const html = renderProperties({ properties: { tags: ["engineer", "ml"] } })
    expect(html).toContain("wikicommit-properties-tags")
    expect(html).toContain("tag-link")
    // slug is "ja/person/yamada-taro" (2 segments deep) -> "../../" to root
    expect(html).toContain('href="../../tags/engineer"')
  })

  it("renders booleans as disabled checkboxes", () => {
    const html = renderProperties({ properties: { flag: true } })
    expect(html).toContain('type="checkbox"')
    expect(html).toContain("checked")
    expect(html).toContain("disabled")
  })

  it("renders numbers in the number span", () => {
    const html = renderProperties({ properties: { count: 42 } })
    expect(html).toContain("wikicommit-properties-number")
    expect(html).toContain("42")
  })

  it("renders null/undefined as an em-dash placeholder", () => {
    const html = renderProperties({ properties: { missing: null } })
    expect(html).toContain("wikicommit-properties-empty")
  })

  it("returns null when showProperties is false, even if properties is non-empty", () => {
    expect(
      renderProperties({ properties: { description: "x" }, showProperties: false }),
    ).toBeNull()
  })

  it("returns null when hideView is true and showProperties is not explicitly true", () => {
    expect(renderProperties({ properties: { description: "x" }, hideView: true })).toBeNull()
  })

  it("renders when showProperties is true even if hideView is also true (per-note override wins)", () => {
    expect(
      renderProperties({
        properties: { description: "x" },
        hideView: true,
        showProperties: true,
      }),
    ).not.toBeNull()
  })

  it("starts collapsed when collapseProperties is true", () => {
    const html = renderProperties({
      properties: { description: "x" },
      collapseProperties: true,
    })
    expect(html).toContain('data-collapsed="true"')
    expect(html).not.toContain(" open")
  })

  // Issue #378 pattern (see WikiCommitSources's own test suite): frontmatter.lang
  // must take priority over the site-wide cfg.locale for the panel's own caption.
  it("uses the ja-JP caption for a ja page even when cfg.locale is unset", () => {
    const html = renderProperties(
      { properties: { description: "x" } },
      { frontmatter: { lang: "ja" } },
    )
    expect(html).toContain("プロパティ")
  })

  it("uses the English caption for an en page even when cfg.locale is ja-JP", () => {
    const html = renderProperties(
      { properties: { description: "x" } },
      { frontmatter: { lang: "en" }, cfg: { locale: "ja-JP" } as unknown as GlobalConfiguration },
    )
    expect(html).toContain(">Properties<")
  })

  // Issue #514, upstream-inherited bug #2: a bare URL followed immediately
  // by sentence-final punctuation (no whitespace in between) must not pull
  // that punctuation into the href.
  it("trims trailing sentence-final punctuation off a bare URL instead of including it in the href", () => {
    const html = renderProperties({
      properties: { description: "詳細は https://example.com/page. を参照" },
    })
    expect(html).toContain('href="https://example.com/page"')
    expect(html).not.toContain('href="https://example.com/page."')
    // The trimmed period itself must still appear as plain text after the link.
    expect(html).toContain(". を参照")
  })

  it("trims a trailing Japanese full stop off a bare URL", () => {
    const html = renderProperties({
      properties: { description: "参考: https://example.com/page。" },
    })
    expect(html).toContain('href="https://example.com/page"')
  })

  it("does not trim a URL that has no trailing punctuation", () => {
    const html = renderProperties({
      properties: { description: "See https://example.com/page for details" },
    })
    expect(html).toContain('href="https://example.com/page"')
  })

  it("does not trim a straight quote/apostrophe that could be the URL's own final character", () => {
    // Deliberately under-trims rather than corrupting a URL whose query
    // string legitimately ends in a straight quote/apostrophe.
    const html = renderProperties({
      properties: { description: "検索: https://example.com/search?q=don't" },
    })
    expect(html).toContain('href="https://example.com/search?q=don\'t"')
  })

  it("trims a trailing typographic ellipsis and curly closing quote off a bare URL", () => {
    const ellipsisHtml = renderProperties({
      properties: { description: "続きはこちら https://example.com/page…" },
    })
    expect(ellipsisHtml).toContain('href="https://example.com/page"')

    const curlyQuoteHtml = renderProperties({
      properties: { description: "彼はこう言った：‘https://example.com/page’" },
    })
    expect(curlyQuoteHtml).toContain('href="https://example.com/page"')
  })

  it("trims an unbalanced wrapping paren off a bare URL while keeping a URL that legitimately ends in a balanced paren", () => {
    const wrapped = renderProperties({
      properties: { description: "参考 (https://example.com/page) を参照" },
    })
    expect(wrapped).toContain('href="https://example.com/page"')

    const wikipediaStyle = renderProperties({
      properties: { description: "See https://en.wikipedia.org/wiki/Foo_(bar) for details" },
    })
    expect(wikipediaStyle).toContain('href="https://en.wikipedia.org/wiki/Foo_(bar)"')
  })

  it("omits a URL match trimmed down to a bare scheme with no host", () => {
    const html = renderProperties({
      properties: { description: "参照: https://...." },
    })
    expect(html).not.toContain("<a")
    expect(html).not.toContain('href="https://')
  })
})
