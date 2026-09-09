import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"

// This plugin ships two locales. **That is not a claim that two is the right
// number** — no record exists of anyone deciding on English and Japanese; both
// files have been here since the plugin's first commit. What has been decided
// is the other half: when to add a third.
//
// **This plugin is not the one holding a third locale up.** Its entire copy is
// one label ("Read in:"); a clumsy translation of it is clumsy and nothing
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
// reader one translated phrase among English sentences.
//
// **A partial locale is not an option today.** `Record<string, typeof enUS>`
// requires every key, so a locale file missing one does not compile. That is a
// guarantee, not a defect — a locale is complete or absent, never
// half-rendered.
//
// **To add a locale**, add it to `locales` below, keyed by the full locale
// string that Quartz puts in `cfg.locale` (this plugin has no LANG_TO_LOCALE
// map — see the next paragraph for why), in the same change as the
// translations themselves.
//
// **This plugin has no `resolveLocale()`, unlike the other three.** It calls
// `i18n(cfg?.locale ?? "en-US")` — one value for the whole site — and never
// reads the rendered page's own `frontmatter.lang`, so on a bilingual wiki its
// text does not follow the page the way the banner's and the sources box's do.
// Whether it should is a separate question that has not been settled; this
// note records the difference so it is not mistaken for an oversight.
//
// **A language with no translation renders in English**, per site. `i18n()`
// falls back to `enUS` for any locale that is not a key of `locales`.
const locales: Record<string, typeof enUS> = {
  "en-US": enUS,
  "ja-JP": jaJP,
}

export function i18n(locale: string) {
  return locales[locale] || enUS
}
