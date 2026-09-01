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
  // must match against (see the comment on entityPathToRelativePath in
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
    // rename keeps its old translated_from verbatim (no auto-migration; the
    // old and new forms are allowed to coexist), so the parent lookup must
    // still resolve it.
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

  it("inherits sources for a translated custom-type page, whose published path drops custom/", () => {
    // convert_wikilinks.py writes .wikicommit/entity/ja/custom/Decision/x.md
    // to content/ja/Decision/x.md (Issue #576), so `relativePath` — which is
    // content-relative — never contains the custom/ segment that
    // translated_from does. A miss here is silent (indistinguishable from
    // "this page has no parent"), so inheritance would just stop working.
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/custom/Decision/adopt-quartz.md" },
      {
        slug: "en/decision/adopt-quartz",
        allFiles: [
          {
            slug: "ja/decision/adopt-quartz",
            relativePath: "ja/Decision/adopt-quartz.md",
            frontmatter: {
              title: "Quartz の採用",
              sources: [{ type: "url", url: "https://example.com/decision" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/decision")
    expect(html).toContain("wikicommit-sources__inherited")
  })

  it("only drops the first custom/ segment of a translated_from path", () => {
    // flatten_custom_type() removes one leading segment so the mapping stays
    // injective; the TypeScript side has to agree or the two disagree about
    // where a doubly-nested type publishes.
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/custom/custom/Decision/x.md" },
      {
        slug: "en/custom/decision/x",
        allFiles: [
          {
            slug: "ja/custom/decision/x",
            relativePath: "ja/custom/Decision/x.md",
            frontmatter: {
              title: "X",
              sources: [{ type: "url", url: "https://example.com/nested" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("https://example.com/nested")
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

  // Issue #558: the per-page attribution layer. A recorded sources[].license
  // has to reach the reader together with the source link and the "this was
  // adapted" statement — the three things CC BY-SA §3(a) asks for.
  it("renders a recorded license next to the source it belongs to", () => {
    const html = renderSources({
      sources: [
        {
          type: "url",
          url: "https://it.wikipedia.org/wiki/Decameron",
          hash: "sha256:abc",
          license: "CC-BY-SA-4.0",
        },
      ],
    })
    expect(html).toContain("CC-BY-SA-4.0")
    expect(html).toContain('href="https://creativecommons.org/licenses/by-sa/4.0/"')
  })

  it("links CC0 to its public domain dedication", () => {
    const html = renderSources({
      sources: [{ type: "url", url: "https://www.wikidata.org/wiki/Q1", license: "CC0-1.0" }],
    })
    expect(html).toContain('href="https://creativecommons.org/publicdomain/zero/1.0/"')
  })

  it("renders a non-Creative-Commons license identifier as plain text", () => {
    const html = renderSources({
      sources: [{ type: "url", url: "https://example.com/a", license: "PDL-1.0" }],
    })
    expect(html).toContain("PDL-1.0")
    expect(html).not.toContain("creativecommons.org")
  })

  it("renders a license recorded on a path or manual source too", () => {
    const html = renderSources({
      sources: [
        { type: "path", path: "raw/paper-2024.pdf", hash: "sha256:abc", license: "CC-BY-4.0" },
        { type: "manual", author: "Taro Yamada", created_at: "2026-06-21", license: "CC-BY-SA-4.0" },
      ],
    })
    expect(html).toContain("CC-BY-4.0")
    expect(html).toContain('href="https://creativecommons.org/licenses/by/4.0/"')
    expect(html).toContain("CC-BY-SA-4.0")
  })

  it("omits the license markup entirely when no license is recorded", () => {
    const html = renderSources({
      sources: [{ type: "url", url: "https://example.com/article", hash: "sha256:def" }],
    })
    expect(html).not.toContain("wikicommit-sources__license")
  })

  it("ignores a blank or non-string license instead of rendering empty parentheses", () => {
    const html = renderSources({
      sources: [
        { type: "url", url: "https://example.com/a", license: "   " },
        { type: "url", url: "https://example.com/b", license: 42 },
      ],
    })
    expect(html).not.toContain("wikicommit-sources__license")
  })

  it("omits the LLM-adaptation claim on a page whose sources are all manual", () => {
    // A `type: manual` source records a human who wrote the page directly, so
    // the generated-by-an-LLM sentence would be a false authorship statement.
    const html = renderSources({
      lang: "en",
      sources: [{ type: "manual", author: "Taro Yamada", created_at: "2026-06-21" }],
    })
    expect(html).not.toContain("summarized and restructured")
    expect(html).not.toContain("wikicommit-sources__notice")
  })

  it("still scopes a displayed license on a manual-only page", () => {
    const html = renderSources({
      lang: "en",
      sources: [
        { type: "manual", author: "Taro Yamada", created_at: "2026-06-21", license: "CC-BY-4.0" },
      ],
    })
    expect(html).toContain("wikicommit-sources__notice")
    expect(html).toContain("not to this page as a whole")
    expect(html).not.toContain("summarized and restructured")
  })

  it("states the adaptation once a single non-manual source is present", () => {
    const html = renderSources({
      lang: "en",
      sources: [
        { type: "manual", author: "Taro Yamada", created_at: "2026-06-21" },
        { type: "url", url: "https://example.com/article", hash: "sha256:abc" },
      ],
    })
    expect(html).toContain("summarized and restructured")
  })

  it("always states that the page adapts its sources, in the page's own language", () => {
    const ja = renderSources({
      lang: "ja",
      sources: [{ type: "url", url: "https://example.com/article" }],
    })
    expect(ja).toContain("wikicommit-sources__notice")
    expect(ja).toContain("要約・再構成")

    const en = renderSources({
      lang: "en",
      sources: [{ type: "url", url: "https://example.com/article" }],
    })
    expect(en).toContain("summarized and restructured")
  })

  // ── derived_from: synthesized pages (Issue #587) ───────────────────────────
  //
  // A synthesized page has no `sources` at all, so before this the box vanished
  // and the page was indistinguishable, on the page itself, from one whose
  // sources had simply been forgotten.

  const groundingPages = [
    {
      slug: "ja/person/yamada-taro",
      relativePath: "ja/Person/yamada-taro.md",
      frontmatter: { title: "山田太郎" },
    },
    {
      slug: "ja/organization/companya",
      relativePath: "ja/Organization/companya.md",
      frontmatter: { title: "CompanyA" },
    },
  ]

  it("renders derived_from pages as links when the page has no sources", () => {
    const html = renderSources(
      {
        title: "合成ページ",
        lang: "ja",
        derived_from: [
          { path: ".wikicommit/entity/ja/Person/yamada-taro.md", source_commit: "abc123" },
          { path: ".wikicommit/entity/ja/Organization/companya.md", source_commit: "def456" },
        ],
      },
      { slug: "ja/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(html).toContain("wikicommit-sources__derived")
    expect(html).toContain("山田太郎")
    expect(html).toContain("CompanyA")
    expect(html).toContain("合成したもの")
  })

  it("lists a derived_from entry whose page is missing, without a link", () => {
    // Dropping it would recreate the gap this closes: a page silently short one
    // line of provenance reads exactly like one that never had it.
    const html = renderSources(
      {
        derived_from: [
          { path: ".wikicommit/entity/ja/Person/yamada-taro.md" },
          { path: ".wikicommit/entity/ja/Person/gone.md" },
        ],
      },
      { slug: "ja/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(html).toContain("山田太郎")
    expect(html).toContain("ja/Person/gone.md")
    expect(html).toContain("wikicommit-sources__unavailable")
  })

  it("lists a derived_from entry whose page is status: removed, without a link", () => {
    const html = renderSources(
      { derived_from: [{ path: ".wikicommit/entity/ja/Person/yamada-taro.md" }] },
      {
        slug: "ja/definedterm/synthesized",
        allFiles: [
          {
            slug: "ja/person/yamada-taro",
            relativePath: "ja/Person/yamada-taro.md",
            frontmatter: { title: "山田太郎", status: "removed" },
          },
        ],
      },
    )
    expect(html).toContain("wikicommit-sources__unavailable")
    expect(html).not.toContain("<a")
  })

  it("resolves a derived_from entry written with the pre-rename .wikicommit/wiki/ prefix", () => {
    const html = renderSources(
      { derived_from: [{ path: ".wikicommit/wiki/ja/Person/yamada-taro.md" }] },
      { slug: "ja/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(html).toContain("山田太郎")
    expect(html).not.toContain("wikicommit-sources__unavailable")
  })

  it("resolves a derived_from entry pointing at a custom-type page", () => {
    // Publishing drops the `custom/` segment, and relativePath is
    // content-relative, so the lookup has to drop it too.
    const html = renderSources(
      { derived_from: [{ path: ".wikicommit/entity/ja/custom/Decision/adopt.md" }] },
      {
        slug: "ja/definedterm/synthesized",
        allFiles: [
          {
            slug: "ja/decision/adopt",
            relativePath: "ja/Decision/adopt.md",
            frontmatter: { title: "Adopt Quartz" },
          },
        ],
      },
    )
    expect(html).toContain("Adopt Quartz")
    expect(html).not.toContain("wikicommit-sources__unavailable")
  })

  it("renders nothing when derived_from is empty or not a list", () => {
    expect(renderSources({ derived_from: [] })).toBeNull()
    expect(
      renderSources({ derived_from: "nope" } as unknown as Record<string, unknown>),
    ).toBeNull()
  })

  it("skips derived_from entries with no usable path instead of throwing", () => {
    const html = renderSources(
      {
        derived_from: [
          { source_commit: "abc123" },
          { path: "" },
          { path: ".wikicommit/entity/ja/Person/yamada-taro.md" },
        ],
      },
      { slug: "ja/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(html).toContain("山田太郎")
  })

  it("inherits derived_from from the parent when translating a synthesized page", () => {
    // A translation carries translated_from, and its parent's provenance lives
    // in derived_from rather than sources — inheritance has to cover both.
    const html = renderSources(
      { translated_from: ".wikicommit/entity/ja/DefinedTerm/synthesized.md" },
      {
        slug: "en/definedterm/synthesized",
        allFiles: [
          ...groundingPages,
          {
            slug: "ja/definedterm/synthesized",
            relativePath: "ja/DefinedTerm/synthesized.md",
            frontmatter: {
              title: "合成ページ",
              derived_from: [{ path: ".wikicommit/entity/ja/Person/yamada-taro.md" }],
            },
          },
        ],
      },
    )
    expect(html).toContain("wikicommit-sources__inherited")
    expect(html).toContain("山田太郎")
  })

  it("renders both blocks when a page somehow carries sources and derived_from", () => {
    const html = renderSources(
      {
        sources: [{ type: "url", url: "https://example.com/article" }],
        derived_from: [{ path: ".wikicommit/entity/ja/Person/yamada-taro.md" }],
      },
      { slug: "ja/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(html).toContain("https://example.com/article")
    expect(html).toContain("wikicommit-sources__derived")
  })

  it("uses the page's own language for the derived_from caption", () => {
    const en = renderSources(
      { lang: "en", derived_from: [{ path: ".wikicommit/entity/ja/Person/yamada-taro.md" }] },
      { slug: "en/definedterm/synthesized", allFiles: groundingPages },
    )
    expect(en).toContain("synthesized from the following pages")
  })

  it("renders nothing for a synthesized page marked status: removed", () => {
    expect(
      renderSources(
        {
          status: "removed",
          derived_from: [{ path: ".wikicommit/entity/ja/Person/yamada-taro.md" }],
        },
        { allFiles: groundingPages },
      ),
    ).toBeNull()
  })
})
