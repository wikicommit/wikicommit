import { describe, expect, it } from "vitest"
import { i18n, resolveLocale } from "./index"
import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

describe("i18n", () => {
  it("selects the ja-JP locale for pages with lang: ja", () => {
    expect(i18n("ja-JP")).toBe(jaJP)
  })

  it("selects the en-US locale for pages with lang: en", () => {
    expect(i18n("en-US")).toBe(enUS)
  })

  it("falls back to en-US for an unsupported locale", () => {
    expect(i18n("fr-FR")).toBe(enUS)
  })

  it("falls back to en-US when no locale is given", () => {
    expect(i18n("")).toBe(enUS)
  })
})

// Issue #378 pattern (see WikiCommitSources/WikiCommitBanner's own i18n
// tests): frontmatter.lang (ISO 639-1) must take priority over the site-wide
// cfg.locale (BCP 47) so each page's own language decides its captions, not
// the site's global default.
describe("resolveLocale", () => {
  it("maps frontmatter.lang ja to ja-JP regardless of cfg.locale", () => {
    expect(resolveLocale("ja", "en-US")).toBe("ja-JP")
  })

  it("maps frontmatter.lang en to en-US regardless of cfg.locale", () => {
    expect(resolveLocale("en", "ja-JP")).toBe("en-US")
  })

  it("falls back to cfg.locale when frontmatter.lang is undefined", () => {
    expect(resolveLocale(undefined, "ja-JP")).toBe("ja-JP")
  })

  it("falls back to cfg.locale when frontmatter.lang is not a string", () => {
    expect(resolveLocale(123, "ja-JP")).toBe("ja-JP")
  })

  it("falls back to cfg.locale when frontmatter.lang is a language this plugin has no locale for", () => {
    expect(resolveLocale("fr", "ja-JP")).toBe("ja-JP")
  })

  it("falls back to en-US when both frontmatter.lang and cfg.locale are absent", () => {
    expect(resolveLocale(undefined, undefined)).toBe("en-US")
  })
})
