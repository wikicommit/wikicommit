import type { GlobalConfiguration, QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { afterEach, describe, expect, it, vi } from "vitest"
import WikiCommitBannerConstructor from "./WikiCommitBanner"

const WikiCommitBanner = WikiCommitBannerConstructor()

type BannerTestOptions = {
  slug?: string
  cfg?: Partial<GlobalConfiguration>
  allFiles?: Array<{ relativePath?: string; slug?: string; frontmatter?: Record<string, unknown> }>
}

function makeProps(
  frontmatter: Record<string, unknown>,
  options: BannerTestOptions = {},
): QuartzComponentProps {
  return {
    fileData: { frontmatter, slug: options.slug },
    cfg: options.cfg,
    allFiles: options.allFiles ?? [],
  } as unknown as QuartzComponentProps
}

function renderBanner(frontmatter: Record<string, unknown>, options: BannerTestOptions = {}): string | null {
  const result = WikiCommitBanner(makeProps(frontmatter, options))
  if (result === null) return null
  return render(result as VNode)
}

describe("WikiCommitBanner", () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it("renders the pending banner when review_status is pending", () => {
    const html = renderBanner({ title: "山田太郎", review_status: "pending" })
    expect(html).toContain("wikicommit-banner--pending")
    expect(html).toContain("This page is unreviewed")
  })

  it("treats a missing review_status as pending", () => {
    const html = renderBanner({ title: "山田太郎" })
    expect(html).toContain("wikicommit-banner--pending")
  })

  it("renders only the report link (no warning banner) when review_status is reviewed", () => {
    const html = renderBanner({ title: "山田太郎", review_status: "reviewed" })
    expect(html).not.toContain("wikicommit-banner--pending")
    expect(html).toContain("wikicommit-banner__report")
    expect(html).toContain("Report an issue")
  })

  it("displays generated_at and generated_by when present", () => {
    const html = renderBanner({
      review_status: "pending",
      generated_at: "2026-06-17",
      generated_by: "claude-sonnet-4-6",
    })
    expect(html).toContain("2026-06-17")
    expect(html).toContain("claude-sonnet-4-6")
  })

  it("falls back to the locale's unknown label when generated_at / generated_by are missing", () => {
    const html = renderBanner({ review_status: "pending" })
    expect(html).toContain("unknown")
  })

  // Issue #453: translation pages carry translated_at/translated_by (a distinct
  // event from generation) instead of generated_at/generated_by, which they
  // never had. Before this fix, every translated page's pending banner showed
  // "unknown" for both fields unconditionally.
  it("displays translated_at and translated_by (under the Translated:/Model: labels) on a translation page", () => {
    const html = renderBanner({
      review_status: "pending",
      translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
      translated_at: "2026-07-01",
      translated_by: "claude-sonnet-4-6",
    })
    expect(html).toContain("Translated:")
    expect(html).toContain("2026-07-01")
    expect(html).toContain("claude-sonnet-4-6")
    expect(html).not.toContain("Generated:")
  })

  it("falls back to the locale's unknown label when translated_at / translated_by are missing on a translation page", () => {
    const html = renderBanner({
      review_status: "pending",
      translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
    })
    expect(html).toContain("Translated:")
    expect(html).toContain("unknown")
  })

  it("does not use translation labels/fields for an ordinary (non-translated) page", () => {
    const html = renderBanner({
      review_status: "pending",
      generated_at: "2026-06-17",
      generated_by: "claude-sonnet-4-6",
    })
    expect(html).toContain("Generated:")
    expect(html).not.toContain("Translated:")
  })

  // Issue #528: isTranslation previously only switched the Translated:/Model:
  // captions — a reader-filed Issue on a translation page carried no signal
  // that the page is a translation, or where the original lives.
  describe("original page pointer in the report body (Issue #528)", () => {
    it("links to the original page's own public URL when it resolves via allFiles", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "Taro Yamada",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
        },
        {
          slug: "en/person/yamada-taro",
          cfg: { baseUrl: "example.github.io/wiki" },
          allFiles: [
            {
              relativePath: "ja/Person/yamada-taro.md",
              slug: "ja/person/yamada-taro",
              frontmatter: { title: "山田太郎" },
            },
          ],
        },
      )
      expect(html).toContain(
        encodeURIComponent("Original page: https://example.github.io/wiki/ja/person/yamada-taro"),
      )
    })

    it("falls back to the raw translated_from path when the parent isn't found in allFiles", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "Taro Yamada",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
        },
        { cfg: { baseUrl: "example.github.io/wiki" } },
      )
      expect(html).toContain(
        encodeURIComponent("Original page: .wikicommit/entity/ja/Person/yamada-taro.md"),
      )
    })

    it("falls back to the raw translated_from path when cfg.baseUrl is unset", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "Taro Yamada",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
        },
        {
          allFiles: [{ relativePath: "ja/Person/yamada-taro.md", slug: "ja/person/yamada-taro" }],
        },
      )
      expect(html).toContain(
        encodeURIComponent("Original page: .wikicommit/entity/ja/Person/yamada-taro.md"),
      )
    })

    it("falls back to the raw translated_from path when the original page itself is status: removed", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "Taro Yamada",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/ja/Person/yamada-taro.md",
        },
        {
          cfg: { baseUrl: "example.github.io/wiki" },
          allFiles: [
            {
              relativePath: "ja/Person/yamada-taro.md",
              slug: "ja/person/yamada-taro",
              frontmatter: { status: "removed" },
            },
          ],
        },
      )
      expect(html).toContain(
        encodeURIComponent("Original page: .wikicommit/entity/ja/Person/yamada-taro.md"),
      )
    })

    it("omits the Original page line entirely for an ordinary (non-translated) page", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner({ title: "OpenAI", review_status: "reviewed" })
      expect(html).not.toContain(encodeURIComponent("Original page:"))
    })

    it("uses the ja-JP label for the original-page line when cfg.locale is ja-JP", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "山田太郎",
          lang: "ja",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/en/Person/taro-yamada.md",
        },
        { cfg: { locale: "ja-JP" } },
      )
      expect(html).toContain(
        encodeURIComponent("原文ページ: .wikicommit/entity/en/Person/taro-yamada.md"),
      )
    })
  })

  it("includes the type (schema name) in the report issue title", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner({
      title: "OpenAI",
      type: "schema:Organization",
      review_status: "reviewed",
    })
    expect(html).toContain(encodeURIComponent("[Report] Organization: OpenAI"))
  })

  it("omits the type segment when frontmatter.type is absent", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner({ title: "OpenAI", review_status: "reviewed" })
    expect(html).toContain(encodeURIComponent("[Report] OpenAI"))
  })

  it("prefills the issue body with the canonical page URL and language", () => {
    // lang: "ja" with no cfg.locale set: the report body's own "Language: ja"
    // line is a literal echo of frontmatter.lang regardless of locale, but
    // the *labels* ("ページ:"/"言語:") now follow frontmatter.lang too
    // (Issue #378) rather than defaulting to English absent an explicit
    // cfg.locale, which is exactly the behavior under test here.
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner(
      { title: "OpenAI", type: "schema:Organization", lang: "ja", review_status: "reviewed" },
      { slug: "ja/organization/openai", cfg: { baseUrl: "example.github.io/wiki" } },
    )
    const expectedBody = ["ページ: https://example.github.io/wiki/ja/organization/openai", "言語: ja"].join(
      "\n",
    )
    expect(html).toContain(`body=${encodeURIComponent(expectedBody)}`)
  })

  it("uses the ja-JP report title prefix and labels when cfg.locale is ja-JP", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner(
      { title: "OpenAI", type: "schema:Organization", lang: "ja", review_status: "reviewed" },
      { slug: "ja/organization/openai", cfg: { locale: "ja-JP", baseUrl: "example.github.io/wiki" } },
    )
    expect(html).toContain(encodeURIComponent("[報告] Organization: OpenAI"))
    expect(html).toContain(encodeURIComponent("ページ: https://example.github.io/wiki/ja/organization/openai"))
    expect(html).toContain(encodeURIComponent("言語: ja"))
    expect(html).toContain("誤りを報告する")
  })

  // Issue #378: WikiCommitBanner used to key captions off cfg.locale (a
  // site-wide setting) unconditionally, so a bilingual wiki's en/ pages
  // showed Japanese captions whenever quartz.config.yaml's locale was ja-JP,
  // and vice versa. frontmatter.lang now takes priority per page.
  it("uses English labels for an en page even when cfg.locale is ja-JP", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner(
      { title: "OpenAI", lang: "en", review_status: "reviewed" },
      { slug: "en/organization/openai", cfg: { locale: "ja-JP" } },
    )
    expect(html).toContain("Report an issue")
    expect(html).not.toContain("誤りを報告する")
  })

  it("falls back to cfg.locale when frontmatter.lang is absent", () => {
    const html = renderBanner(
      { title: "OpenAI", review_status: "pending" },
      { cfg: { locale: "ja-JP" } },
    )
    expect(html).toContain("このページは未レビューです")
  })

  it("falls back to cfg.locale when frontmatter.lang is not a locale this plugin ships", () => {
    const html = renderBanner(
      { title: "OpenAI", lang: "fr", review_status: "pending" },
      { cfg: { locale: "ja-JP" } },
    )
    expect(html).toContain("このページは未レビューです")
  })

  it("falls back to '#' for the report link when GITHUB_REPOSITORY is unset", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "")
    const html = renderBanner({ title: "OpenAI", review_status: "reviewed" })
    expect(html).toContain('href="#"')
  })

  it("renders nothing on a removed page, even when review_status is reviewed", () => {
    const html = renderBanner({ title: "OpenAI", review_status: "reviewed", status: "removed" })
    expect(html).toBeNull()
  })

  it("renders nothing on a removed page that is still pending", () => {
    const html = renderBanner({ title: "OpenAI", review_status: "pending", status: "removed" })
    expect(html).toBeNull()
  })

  // Issue #407: convert_wikilinks.py's generate_root_index() embeds site-wide
  // counts (and, if configured, the theme) as frontmatter on the
  // build-generated content/index.md only. WikiCommitBanner renders them
  // whenever they're present, regardless of slug — see the component's own
  // comment on why it doesn't hardcode fileData.slug === "index".
  it("renders the site summary when wikicommit_page_count/reviewed_count are present", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "reviewed",
      wikicommit_page_count: 42,
      wikicommit_reviewed_count: 30,
    })
    expect(html).toContain("wikicommit-site-summary")
    expect(html).toContain("42")
    expect(html).toContain("30")
  })

  it("renders the theme line when wikicommit_theme is present", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "reviewed",
      wikicommit_page_count: 5,
      wikicommit_reviewed_count: 2,
      wikicommit_theme: "社内技術ナレッジベース",
    })
    expect(html).toContain("wikicommit-site-summary__theme")
    expect(html).toContain("社内技術ナレッジベース")
  })

  it("omits the theme line when wikicommit_theme is absent", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "reviewed",
      wikicommit_page_count: 5,
      wikicommit_reviewed_count: 2,
    })
    expect(html).toContain("wikicommit-site-summary")
    expect(html).not.toContain("wikicommit-site-summary__theme")
  })

  it("does not render the site summary on an ordinary page (no wikicommit_page_count)", () => {
    const html = renderBanner({ title: "山田太郎", review_status: "reviewed" })
    expect(html).not.toContain("wikicommit-site-summary")
  })

  it("renders the site summary alongside the pending banner when the root page happens to be pending", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "pending",
      wikicommit_page_count: 1,
      wikicommit_reviewed_count: 0,
    })
    expect(html).toContain("wikicommit-site-summary")
    expect(html).toContain("wikicommit-banner--pending")
  })

  it("renders a zero page count (brand-new wiki) rather than omitting the summary", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "reviewed",
      wikicommit_page_count: 0,
      wikicommit_reviewed_count: 0,
    })
    expect(html).toContain("wikicommit-site-summary")
  })

  it("strips a trailing slash from cfg.baseUrl before building the page URL", () => {
    vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
    const html = renderBanner(
      { title: "OpenAI", review_status: "reviewed" },
      { slug: "ja/organization/openai", cfg: { baseUrl: "example.github.io/wiki/" } },
    )
    expect(html).toContain(
      encodeURIComponent("Page: https://example.github.io/wiki/ja/organization/openai"),
    )
  })
})
