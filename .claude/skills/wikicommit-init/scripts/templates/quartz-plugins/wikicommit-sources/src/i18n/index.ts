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
// **The set is kept in step elsewhere**: `locales` *and* `LANG_TO_LOCALE`
// below, the other three WikiCommit plugins, convert_wikilinks.py's *_LABELS
// dicts and init.py's WIKICOMMIT_UI_LANGS.
// `tests/test_ui_language_fallback_disclosure.py` fails if they disagree.
// Adding to only one of `locales` / `LANG_TO_LOCALE` is otherwise silent: a
// locale absent from `LANG_TO_LOCALE` is never selected, and a language
// mapped to a locale that is not in `locales` falls back to English.
//
// **A language outside the ten renders in English**, per page. On such a
// wiki, this plugin's text is English while the page body and the Quartz
// chrome around it are not.
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

// frontmatter.lang is an ISO 639-1 code (see CLAUDE.md's frontmatter spec),
// while the keys above are BCP 47 tags, so an explicit map bridges the two.
const LANG_TO_LOCALE: Record<string, string> = {
  en: "en-US",
  ja: "ja-JP",
  de: "de-DE",
  es: "es-ES",
  fr: "fr-FR",
  it: "it-IT",
  pl: "pl-PL",
  pt: "pt-BR",
  ru: "ru-RU",
  zh: "zh-CN",
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
