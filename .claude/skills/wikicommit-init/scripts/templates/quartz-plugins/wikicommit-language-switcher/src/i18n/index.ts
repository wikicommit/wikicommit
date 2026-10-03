import enUS from "./locales/en-US"
import jaJP from "./locales/ja-JP"
import deDE from "./locales/de-DE"
import esES from "./locales/es-ES"
import frFR from "./locales/fr-FR"
import itIT from "./locales/it-IT"
import plPL from "./locales/pl-PL"
import ptBR from "./locales/pt-BR"
import ruRU from "./locales/ru-RU"
import zhCN from "./locales/zh-CN"

// This plugin ships ten locales: en, ja, de, es, fr, it, ru, zh, pt and pl
// (Issue #1017). **The set is fixed by an external standard, not by which
// wikis happen to exist**: it is the ten languages the Wikipedia portal
// (wikipedia.org) lists around its globe. Before #1017 the plugin shipped en
// and ja only, and "add a language when a wiki in it appears" answered every
// new language with "because a pilot happened to use it".
//
// **Do not widen the set past these ten on the same reasoning.** The
// community-derived plugins (explorer / graph / search) carry 30 locales
// because that is the set their upstream fork already had; that is an
// inherited exception, not a target for this plugin.
//
// **The non-English locales were produced by an LLM from the English.** Some
// keys carry claims — what this wiki does and does not vouch for — and each
// was translated to say no more than the English says ("checked against
// sources" as compared, not verified). If a translation reads stronger than
// the English, fix the translation; the English is canonical.
//
// **A partial locale is not an option.** `Record<string, typeof enUS>`
// requires every key, so a locale file missing one does not compile. That is a
// guarantee, not a defect — a locale is complete or absent, never
// half-rendered.
//
// **The set is kept in step elsewhere**: `locales` below (keyed by the full
// locale string Quartz puts in `cfg.locale`), the other three WikiCommit
// plugins, convert_wikilinks.py's *_LABELS dicts and init.py's
// WIKICOMMIT_UI_LANGS. `tests/test_ui_language_fallback_disclosure.py` fails
// if they disagree.
//
// **This plugin has no `resolveLocale()`, unlike the other three.** It calls
// `i18n(cfg?.locale ?? "en-US")` — one value for the whole site — and never
// reads the rendered page's own `frontmatter.lang`, so on a bilingual wiki its
// text does not follow the page the way the banner's and the sources box's do.
// Whether it should is a separate question that has not been settled; this
// note records the difference so it is not mistaken for an oversight.
//
// **A language outside the ten renders in English**, per site. `i18n()`
// falls back to `enUS` for any locale that is not a key of `locales`.
const locales: Record<string, typeof enUS> = {
  "en-US": enUS,
  "ja-JP": jaJP,
  "de-DE": deDE,
  "es-ES": esES,
  "fr-FR": frFR,
  "it-IT": itIT,
  "pl-PL": plPL,
  "pt-BR": ptBR,
  "ru-RU": ruRU,
  "zh-CN": zhCN,
}

export function i18n(locale: string) {
  return locales[locale] || enUS
}
