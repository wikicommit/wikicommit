import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

// This plugin ships two locales. **That is not a claim that two is the right
// number** — no record exists of anyone deciding on English and Japanese; both
// files have been here since the plugin's first commit. What has been decided
// is the other half: when to add a third.
//
// **Adding one is blocked on verification, not on translation.** A translation
// can be produced for any of these strings at any time. What this project has
// no way to do is check that the result says what the English says, and the
// cost of getting that wrong is not uniform across the keys:
//
//   - Most keys are plain labels ("Sources", "unknown"). A clumsy
//     translation is clumsy and nothing more.
//   - A minority carry claims — that a page is a recomposition of its
//     sources rather than the sources themselves, where a page inherited
//     its sources from, and what those sources permit. Those sentences
//     exist specifically to keep this wiki from overstating what it
//     knows, and its readers from overstating what they may reuse.
//
// **The second kind fails invisibly.** Left in English it fails visibly: a
// reader who cannot read it knows they cannot. Mistranslated slightly stronger,
// it reads fine and the reader believes something this wiki deliberately does
// not say — and nobody here can see that it happened.
//
// **A partial locale is not an option today.** `Record<string, typeof enUS>`
// requires every key, so a locale file missing one does not compile. That is a
// guarantee, not a defect — a locale is complete or absent, never half-rendered
// — but it also means the easy 80% cannot be shipped without the hard 20%.
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
