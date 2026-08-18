import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

const locales: Record<string, typeof enUS> = {
  "en-US": enUS,
  "ja-JP": jaJP,
}

export function i18n(locale: string) {
  return locales[locale] || enUS
}

// frontmatter.lang is an ISO 639-1 code (see CLAUDE.md's frontmatter spec),
// while the keys above are BCP 47 tags, so an explicit map bridges the two.
const LANG_TO_LOCALE: Record<string, string> = {
  en: "en-US",
  ja: "ja-JP",
}

// Prefers the rendered page's own frontmatter.lang over the site-wide
// cfg.locale (quartz.config.yaml), so a bilingual wiki shows Japanese
// captions on ja/ pages and English captions on en/ pages regardless of the
// site's configured locale (Issue #378 — WikiCommitSources/WikiCommitBanner
// previously used cfg.locale unconditionally, so an en/ translation page
// rendered with Japanese captions whenever the site locale was ja-JP, and
// vice versa). Falls back to cfg.locale, then "en-US", when frontmatter.lang
// is missing or not one of the locales this plugin ships translations for.
export function resolveLocale(frontmatterLang: unknown, cfgLocale: string | undefined): string {
  if (typeof frontmatterLang === "string") {
    const mapped = LANG_TO_LOCALE[frontmatterLang]
    if (mapped) return mapped
  }
  return cfgLocale ?? "en-US"
}
