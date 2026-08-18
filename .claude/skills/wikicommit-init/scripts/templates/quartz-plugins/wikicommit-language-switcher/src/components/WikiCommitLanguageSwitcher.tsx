import type {
  FullSlug,
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "@quartz-community/types"
// Import from the "./path" subpath (not the package root) to avoid pulling in
// the unrelated jsx.ts module, whose hast-util-to-jsx-runtime dependency is
// missing from @quartz-community/utils's own package.json.
import { resolveRelative } from "@quartz-community/utils/path"
import { i18n } from "../i18n"
import style from "./styles/wikicommit-language-switcher.scss"

// Native (endonym) display names for common ISO 639-1 codes, shown
// regardless of the reader's own UI locale (the Wikipedia langlink
// convention: a French reader recognizes "日本語" as Japanese without
// reading Japanese). Falls back to the uppercased code for anything not
// listed here so an unrecognized `lang` value still renders.
const LANGUAGE_NAMES: Record<string, string> = {
  ja: "日本語",
  en: "English",
  zh: "中文",
  ko: "한국어",
  fr: "Français",
  de: "Deutsch",
  es: "Español",
  pt: "Português",
  ru: "Русский",
  it: "Italiano",
  vi: "Tiếng Việt",
  th: "ไทย",
  id: "Bahasa Indonesia",
  ar: "العربية",
}

function languageName(lang: string): string {
  return LANGUAGE_NAMES[lang] ?? lang.toUpperCase()
}

interface TypeSlugKey {
  lang: string
  key: string
}

// The Quartz build mirrors .wikicommit/entity/<lang>/<Type>/<slug>.md 1:1 into
// content/<lang>/<Type>/<slug>.md (see scripts/convert_wikilinks.py), so the
// first path segment of relativePath is always the page's language and the
// remainder is the Type/slug key that identifies the same entity across
// languages. Only 2-letter segments are treated as a lang directory so the
// language-neutral content/assets/ tree (mirrored from
// .wikicommit/entity/assets/) and the generated root content/index.md (a bare
// "index.md" relativePath, with no "/") are excluded rather than misread as
// a lang directory.
//
// Duplicated (not imported) in wikicommit-breadcrumbs and wikicommit-explorer
// — the 3 plugins are independent npm packages with no shared workspace, so
// there's no runtime-shareable module between them. tests/test_quartz_plugins_lang_segment_sync.py
// asserts this literal stays byte-identical across all 3 copies (Issue #228).
const LANG_SEGMENT_RE = /^[a-z]{2}$/

function typeSlugKey(relativePath: string): TypeSlugKey | null {
  const slashIndex = relativePath.indexOf("/")
  if (slashIndex === -1) return null
  const lang = relativePath.slice(0, slashIndex)
  if (!LANG_SEGMENT_RE.test(lang)) return null
  const key = relativePath.slice(slashIndex + 1)
  if (!key) return null
  return { lang, key }
}

// Groups every file by its Type/slug key once per build (O(pages)), instead
// of each page's render scanning the full allFiles array for its own siblings
// (O(pages) per page, i.e. O(pages^2) per build). Cached on ctx below,
// mirroring the ctx.wikicommitBreadcrumbsTrie caching in the sibling
// wikicommit-breadcrumbs plugin.
function buildLanguageIndex(
  allFiles: QuartzComponentProps["allFiles"],
): Map<string, Map<string, FullSlug>> {
  const index = new Map<string, Map<string, FullSlug>>()
  for (const file of allFiles) {
    if (file.frontmatter?.status === "removed") continue
    const relativePath = file.relativePath as string | undefined
    if (!relativePath) continue
    const parsed = typeSlugKey(relativePath)
    if (!parsed) continue
    const slug = file.slug as FullSlug | undefined
    if (!slug) continue
    // Keyed by lang so that, if the same Type/slug somehow appears twice
    // under one language (shouldn't happen; check_orphans.py blocks
    // duplicates), the last one wins rather than rendering a duplicate entry.
    let byLang = index.get(parsed.key)
    if (!byLang) {
      byLang = new Map<string, FullSlug>()
      index.set(parsed.key, byLang)
    }
    byLang.set(parsed.lang, slug)
  }
  return index
}

interface LanguageEntry {
  lang: string
  href: string
  isCurrent: boolean
}

const WikiCommitLanguageSwitcher: QuartzComponent = ({
  fileData,
  allFiles,
  cfg,
  ctx,
}: QuartzComponentProps) => {
  const frontmatter = fileData.frontmatter
  if (frontmatter?.status === "removed") return null

  const currentRelativePath = fileData.relativePath as string | undefined
  if (!currentRelativePath) return null
  const current = typeSlugKey(currentRelativePath)
  if (!current) return null

  const currentSlug = fileData.slug as FullSlug | undefined
  if (!currentSlug) return null

  const typedCtx = (ctx ?? {}) as Record<string, unknown> as {
    wikicommitLanguageIndex?: Map<string, Map<string, FullSlug>>
  }
  typedCtx.wikicommitLanguageIndex ??= buildLanguageIndex(allFiles)
  const siblings = typedCtx.wikicommitLanguageIndex.get(current.key) ?? new Map<string, FullSlug>()

  // Nothing to switch to: either this is the only language for this
  // Type/slug, or (defensively) the current page didn't match itself above.
  if (siblings.size <= 1) return null

  const t = i18n(cfg?.locale ?? "en-US").components.wikicommitLanguageSwitcher

  const entries: LanguageEntry[] = [...siblings.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([lang, slug]) => ({
      lang,
      href: lang === current.lang ? "" : resolveRelative(currentSlug, slug),
      isCurrent: lang === current.lang,
    }))

  return (
    <div class="wikicommit-language-switcher">
      <span class="wikicommit-language-switcher__label">{t.label}</span>
      <ul class="wikicommit-language-switcher__list">
        {entries.map((entry) => (
          <li key={entry.lang} class="wikicommit-language-switcher__item">
            {entry.isCurrent ? (
              <span class="wikicommit-language-switcher__current" aria-current="true">
                {languageName(entry.lang)}
              </span>
            ) : (
              <a href={entry.href} class="wikicommit-language-switcher__link">
                {languageName(entry.lang)}
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

WikiCommitLanguageSwitcher.css = style

export default (() => WikiCommitLanguageSwitcher) satisfies QuartzComponentConstructor
