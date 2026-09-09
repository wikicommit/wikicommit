import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

// This plugin ships two locales. **That is not a claim that two is the right
// number** — no record exists of anyone deciding on English and Japanese; both
// files have been here since the plugin's first commit. What has been decided
// is the other half: when to add a third.
//
// **This plugin is not the one holding a third locale up.** Its entire copy is
// one label ("Properties"); a clumsy translation of it is clumsy and nothing
// more. What gates a third locale lives in the banner and the sources box,
// whose copy carries claims — what this wiki does and does not vouch for,
// where a page came from, what its sources permit. A translation of those can
// be produced at any time; what this project has no way to do is check that
// the result says what the English says, and a sentence mistranslated slightly
// stronger reads fine while the reader believes something this wiki
// deliberately does not say.
//
// **So the four plugins gain a locale together or not at all.** A wiki
// installs all four from one init, and translating this label alone leaves the
// reader one translated word among English sentences.
//
// **A partial locale is not an option today.** `Record<string, typeof enUS>`
// requires every key, so a locale file missing one does not compile. That is a
// guarantee, not a defect — a locale is complete or absent, never
// half-rendered.
//
// **To add a locale**, add it to `locales` *and* to `LANG_TO_LOCALE` below, in
// the same change as the translations themselves. Adding to only one is silent:
// a locale absent from `LANG_TO_LOCALE` is never selected, and a language
// mapped to a locale that is not in `locales` falls back to English.
//
// **A language with no translation renders in English**, per page. On a wiki
// whose pages are in a third language, that shows as this plugin's text being
// English while the page body and the Quartz chrome around it are not.
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
// cfg.locale (quartz.config.yaml), matching WikiCommitSources/WikiCommitBanner
// (Issue #378) — a bilingual wiki should show Japanese captions on ja/ pages
// and English captions on en/ pages regardless of the site's configured
// locale. Falls back to cfg.locale, then "en-US", when frontmatter.lang is
// missing or not one of the locales this plugin ships translations for.
export function resolveLocale(frontmatterLang: unknown, cfgLocale: string | undefined): string {
  if (typeof frontmatterLang === "string") {
    const mapped = LANG_TO_LOCALE[frontmatterLang]
    if (mapped) return mapped
  }
  return cfgLocale ?? "en-US"
}
