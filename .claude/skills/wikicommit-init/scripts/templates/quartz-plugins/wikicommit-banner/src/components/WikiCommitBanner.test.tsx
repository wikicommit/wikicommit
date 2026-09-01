import type { GlobalConfiguration, QuartzComponentProps } from "@quartz-community/types"
import type { VNode } from "preact"
import render from "preact-render-to-string"
import { afterEach, describe, expect, it, vi } from "vitest"
import WikiCommitBannerConstructor from "./WikiCommitBanner"

const WikiCommitBanner = WikiCommitBannerConstructor()

type BannerTestOptions = {
  slug?: string
  relativePath?: string
  cfg?: Partial<GlobalConfiguration>
  allFiles?: Array<{ relativePath?: string; slug?: string; frontmatter?: Record<string, unknown> }>
}

function makeProps(
  frontmatter: Record<string, unknown>,
  options: BannerTestOptions = {},
): QuartzComponentProps {
  return {
    fileData: { frontmatter, slug: options.slug, relativePath: options.relativePath },
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

  // Issue #663: `reviewed` said a review happened without saying whose judgment
  // it was — the reviewer's name existed only as a git commit trailer, which no
  // reader of the published site sees.
  describe("reviewer attribution on a reviewed page", () => {
    it("names the reviewer and links to their GitHub profile", () => {
      const html = renderBanner({
        title: "山田太郎",
        review_status: "reviewed",
        reviewed_by: "octocat",
      })
      expect(html).toContain("Reviewed by:")
      expect(html).toContain('href="https://github.com/octocat"')
      expect(html).toContain(">octocat<")
    })

    it("falls back to the previous markup when the field is absent", () => {
      const withField = renderBanner({
        title: "山田太郎",
        review_status: "reviewed",
        reviewed_by: "octocat",
      })
      const without = renderBanner({ title: "山田太郎", review_status: "reviewed" })
      // Pages reviewed before the field existed are not back-filled, and a wiki
      // that never runs review-issue-close-sync.yml never gets one — so absence
      // is the normal state, not a gap worth labelling. It must not surface as
      // an empty label or as the "unknown" placeholder the pending branch uses.
      expect(without).not.toContain("Reviewed by:")
      expect(without).not.toContain("unknown")
      expect(without).not.toBe(withField)
      expect(without).toContain("Report an issue")
    })

    it("ignores a present-but-blank value rather than rendering an empty link", () => {
      // The report link's own href is a github.com URL whenever
      // GITHUB_REPOSITORY is set, and GitHub Actions sets it on every step —
      // so the "no github.com link at all" assertion below only means "no
      // reviewer link" once the variable is stubbed away (same trap the
      // review-status-link suite documents).
      vi.stubEnv("GITHUB_REPOSITORY", undefined)
      const html = renderBanner({
        title: "山田太郎",
        review_status: "reviewed",
        reviewed_by: "   ",
      })
      expect(html).not.toContain("Reviewed by:")
      expect(html).not.toContain("https://github.com/")
    })

    it("ignores a non-string value", () => {
      const html = renderBanner({ title: "山田太郎", review_status: "reviewed", reviewed_by: 42 })
      expect(html).not.toContain("Reviewed by:")
    })

    it("does not show a reviewer on a pending page", () => {
      // A pending page has no reviewer by definition; a stale value left behind
      // by a regeneration (which returns the page to pending) must not read as
      // if someone had reviewed this version.
      // Stubbed for the same reason as above: the report link is a github.com
      // URL under an ambient GITHUB_REPOSITORY, so leaving it unstubbed would
      // make this assertion depend on the repository the tests happen to run in.
      vi.stubEnv("GITHUB_REPOSITORY", undefined)
      const html = renderBanner({
        title: "山田太郎",
        review_status: "pending",
        reviewed_by: "octocat",
      })
      expect(html).toContain("wikicommit-banner--pending")
      expect(html).not.toContain("Reviewed by:")
      expect(html).not.toContain("https://github.com/octocat")
    })

    it("renders nothing on a removed page even with a reviewer", () => {
      const html = renderBanner({
        title: "山田太郎",
        review_status: "reviewed",
        reviewed_by: "octocat",
        status: "removed",
      })
      expect(html).toBeNull()
    })

    it("uses the Japanese label on a ja page", () => {
      const html = renderBanner({
        title: "山田太郎",
        lang: "ja",
        review_status: "reviewed",
        reviewed_by: "octocat",
      })
      expect(html).toContain("レビュー者:")
    })
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

  // Issue #579: the banner said the page was unreviewed without offering any
  // way to reach the place that review actually happens.
  describe("review-status search link (Issue #579)", () => {
    const pendingPage = {
      title: "山田太郎",
      review_status: "pending",
      type: "schema:Person",
      lang: "ja",
    }
    const pageLocation = { relativePath: "ja/Person/yamada-taro.md" }

    function reviewLinkHref(html: string | null): string | undefined {
      return html?.match(/href="([^"]*\/issues\?q=[^"]*)"/)?.[1]
    }

    function searchQuery(html: string | null): string {
      const href = reviewLinkHref(html)
      expect(href).toBeDefined()
      return decodeURIComponent(href!.split("?q=")[1] ?? "")
    }

    it("links to a review-tracking Issue search on a pending page", () => {
      // The label follows the page's own lang, like every other caption here.
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(pendingPage, pageLocation)
      expect(html).toContain("このページのレビュー状況を見る")
      expect(reviewLinkHref(html)).toContain("https://github.com/wikicommit-dev/example-wiki/issues?q=")
    })

    it("labels the link in English on an English page", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        { review_status: "pending", type: "schema:Person", lang: "en" },
        { relativePath: "en/Person/yamada-taro.md" },
      )
      expect(html).toContain("Check this page's review status")
      expect(searchQuery(html)).toContain('"Person/yamada-taro (en)"')
    })

    it("filters the search by open state, the tracking label and the title", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const query = searchQuery(renderBanner(pendingPage, pageLocation))
      // is:open is what keeps a regenerated page (which gets a *new* tracking
      // Issue) from pointing at the closed one left behind by the last round.
      expect(query).toContain("is:open")
      expect(query).toContain("label:wikicommit-review")
      expect(query).toContain("in:title")
      expect(query).toContain('"Person/yamada-taro (ja)"')
    })

    it("keys the search on type/slug/lang, never on the page title", () => {
      // A regeneration can change `title` while type/slug/lang stay fixed, so
      // a title-keyed link would go stale every time a page is rebuilt.
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const query = searchQuery(renderBanner(pendingPage, pageLocation))
      expect(query).not.toContain("山田太郎")
    })

    it("keeps a custom type's full type name in the search key", () => {
      // Publishing drops the custom/ segment from the *path* (Issue #576), but
      // wikicommit-merge titles the Issue with the frontmatter type, which
      // keeps it.
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        { review_status: "pending", type: "schema:custom/Decision", lang: "ja" },
        { relativePath: "ja/Decision/adopt-quartz.md" },
      )
      expect(searchQuery(html)).toContain('"custom/Decision/adopt-quartz (ja)"')
    })

    it("does not offer the link on a reviewed page", () => {
      // Its tracking Issue is closed; the report link stays for reporting an
      // error found later (Issue #245).
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner({ ...pendingPage, review_status: "reviewed" }, pageLocation)
      expect(html).not.toContain("このページのレビュー状況を見る")
      expect(reviewLinkHref(html)).toBeUndefined()
      expect(html).toContain("誤りを報告する")
    })

    it("renders nothing at all on a removed page, as before", () => {
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      expect(renderBanner({ ...pendingPage, status: "removed" }, pageLocation)).toBeNull()
    })

    it("omits the link when GITHUB_REPOSITORY is unset", () => {
      // The report link keeps its historical "#" fallback; this one is dropped
      // instead, since a search URL with no repository cannot be made to point
      // anywhere meaningful.
      // Stub the variable away rather than relying on the ambient environment:
      // GitHub Actions sets GITHUB_REPOSITORY on every step, so an unstubbed
      // read would see the real repository and this assertion would fail in CI
      // while passing locally.
      vi.stubEnv("GITHUB_REPOSITORY", undefined)
      const html = renderBanner(pendingPage, pageLocation)
      expect(html).toContain("wikicommit-banner--pending")
      expect(reviewLinkHref(html)).toBeUndefined()
    })

    it("omits the link when the search key cannot be built", () => {
      // type, lang and the file path are each required. Quartz's own folder
      // and tag pages have none of them (no frontmatter), and no tracking
      // Issue either, so they must not get a link that always finds nothing.
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      expect(reviewLinkHref(renderBanner({ review_status: "pending" }, {}))).toBeUndefined()
      expect(
        reviewLinkHref(renderBanner({ review_status: "pending", lang: "ja" }, pageLocation)),
      ).toBeUndefined()
      expect(
        reviewLinkHref(renderBanner({ review_status: "pending", type: "schema:Person" }, pageLocation)),
      ).toBeUndefined()
      expect(reviewLinkHref(renderBanner(pendingPage, {}))).toBeUndefined()
    })
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

    it("resolves the original page of a translated custom-type page, whose published path drops custom/", () => {
      // convert_wikilinks.py writes .wikicommit/entity/ja/custom/Decision/x.md
      // to content/ja/Decision/x.md (Issue #576), so `relativePath` never
      // carries the custom/ segment translated_from does. Without the same
      // flattening here the lookup misses and the banner quietly degrades to
      // the raw-path fallback below.
      vi.stubEnv("GITHUB_REPOSITORY", "wikicommit-dev/example-wiki")
      const html = renderBanner(
        {
          title: "Adopting Quartz",
          review_status: "reviewed",
          translated_from: ".wikicommit/entity/ja/custom/Decision/adopt-quartz.md",
        },
        {
          slug: "en/decision/adopt-quartz",
          cfg: { baseUrl: "example.github.io/wiki" },
          allFiles: [
            {
              relativePath: "ja/Decision/adopt-quartz.md",
              slug: "ja/decision/adopt-quartz",
              frontmatter: { title: "Quartz の採用" },
            },
          ],
        },
      )
      expect(html).toContain(
        encodeURIComponent("Original page: https://example.github.io/wiki/ja/decision/adopt-quartz"),
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
  // counts as frontmatter on the build-generated content/index.md only.
  // WikiCommitBanner renders them whenever they're present, regardless of slug
  // — see the component's own comment on why it doesn't hardcode
  // fileData.slug === "index".
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

  // Issue #664: "Reviewed: 0" on the front page reads as "nobody cares about
  // this project" to a first-time reader. The number stays — hiding it gives up
  // the honesty it was added for — and a caption says what it counts.
  describe("review-count caption", () => {
    it("explains what the count means, keeping the number", () => {
      const html = renderBanner({
        title: "Wiki",
        review_status: "reviewed",
        wikicommit_page_count: 486,
        wikicommit_reviewed_count: 0,
      })
      expect(html).toContain("wikicommit-site-summary__note")
      expect(html).toContain("486")
      // The zero is still shown; only its framing changed.
      expect(html).toContain(">0<")
      expect(html).toContain("published as soon as an LLM generates it")
    })

    it("does not invite the reader to review anything", () => {
      // This wiki does not take outside reviewers, so a call to participate
      // would be addressed to someone who cannot act on it.
      const html = renderBanner({
        title: "Wiki",
        review_status: "reviewed",
        wikicommit_page_count: 486,
        wikicommit_reviewed_count: 0,
      })
      for (const word of ["Help", "help review", "Join", "Contribute", "Sign up"]) {
        expect(html).not.toContain(word)
      }
    })

    it("uses the Japanese caption on a ja root page", () => {
      const html = renderBanner({
        title: "Wiki",
        lang: "ja",
        review_status: "reviewed",
        wikicommit_page_count: 486,
        wikicommit_reviewed_count: 0,
      })
      expect(html).toContain("人によるレビュー済み:")
      expect(html).toContain("人が内容を確認した件数")
    })

    it("is not rendered on a page without the site summary", () => {
      const html = renderBanner({ title: "山田太郎", review_status: "reviewed" })
      expect(html).not.toContain("wikicommit-site-summary__note")
    })
  })

  // Issue #670: config.yml's `theme` is an LLM-facing scope instruction, not
  // reader-facing copy, so the banner no longer renders it. A stale
  // wikicommit_theme left on a previously built content/index.md must not
  // resurrect the line.
  it("never renders a theme line, even when wikicommit_theme is present", () => {
    const html = renderBanner({
      title: "Wiki",
      review_status: "reviewed",
      wikicommit_page_count: 5,
      wikicommit_reviewed_count: 2,
      wikicommit_theme: "社内技術ナレッジベース",
    })
    expect(html).toContain("wikicommit-site-summary")
    expect(html).not.toContain("wikicommit-site-summary__theme")
    expect(html).not.toContain("社内技術ナレッジベース")
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
