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
import { i18n, resolveLocale } from "../i18n"
import style from "./styles/wikicommit-sources.scss"

interface SourceEntry {
  type?: string
  path?: string
  url?: string
  author?: string
  created_at?: unknown
  license?: unknown
}

// A synthesized page (/wikicommit-synthesize, Issue #283) records where it came
// from in `derived_from` instead of `sources` — the two are mutually exclusive,
// like `translated_from`. Until Issue #587 nothing rendered it, so a synthesized
// page showed no provenance at all and was indistinguishable, on the page
// itself, from one whose `sources` had simply been forgotten. That is the worst
// page kind to leave unattributed: it restates other pages' claims.
interface DerivedEntry {
  path?: string
  source_commit?: unknown
}

// One `derived_from` entry after lookup. `unavailable` marks a page that is
// gone or `status: removed`: it is still listed, without a link. Dropping it
// would recreate the very gap this exists to close — a page silently short one
// line of provenance reads exactly like one that never had it.
interface ResolvedDerivation {
  label: string
  href?: string
  unavailable: boolean
}

interface ResolvedProvenance {
  sources: SourceEntry[]
  derivations: ResolvedDerivation[]
  inherited: boolean
  parentTitle?: string
  parentHref?: string
}

function asSourceList(value: unknown): SourceEntry[] {
  return Array.isArray(value) ? (value as SourceEntry[]) : []
}

function asDerivedList(value: unknown): DerivedEntry[] {
  return Array.isArray(value) ? (value as DerivedEntry[]) : []
}

// Builds the canonical deed URL for a Creative Commons SPDX identifier, so a
// recorded `license` renders as "name + URI" — what CC BY-SA §3(a) asks for,
// and what a bare name alone does not give (Issue #558). Derived from the
// identifier's own shape rather than a lookup table so every CC variant works
// without maintaining a list. Any other identifier (a bespoke municipal terms
// of use, PDL-1.0, all-rights-reserved, ...) renders as plain text: WikiCommit
// records and displays what the operator wrote, it does not decide what a
// license means.
const CC_LICENSE_RE = /^CC-(BY(?:-NC)?(?:-SA|-ND)?)-(\d(?:\.\d)?)$/i

function licenseHref(license: string): string | undefined {
  if (/^CC0-1\.0$/i.test(license)) {
    return "https://creativecommons.org/publicdomain/zero/1.0/"
  }
  const m = CC_LICENSE_RE.exec(license)
  const variant = m?.[1]
  const version = m?.[2]
  if (!variant || !version) return undefined
  return `https://creativecommons.org/licenses/${variant.toLowerCase()}/${version}/`
}

function renderLicense(license: unknown) {
  if (typeof license !== "string" || !license.trim()) return null
  const value = license.trim()
  const href = licenseHref(value)
  return (
    <span class="wikicommit-sources__license">
      {" ("}
      {href ? (
        // Deliberately not rel="license": per the HTML spec that keyword says the
        // linked document is the license *of the current page*, which is exactly
        // the claim the adaptation notice below disclaims (a page can merge several
        // differently-licensed sources). Issue #558.
        <a href={href} class="wikicommit-sources__license-link" target="_blank" rel="noopener noreferrer">
          {value}
        </a>
      ) : (
        value
      )}
      {")"}
    </span>
  )
}

// YAML parses an unquoted YYYY-MM-DD scalar (e.g. `created_at: 2026-06-21`) as
// a Date, not a string, so `created_at` must be coerced defensively here.
function formatDate(value: unknown): string | undefined {
  if (value instanceof Date) return value.toISOString().slice(0, 10)
  if (typeof value === "string" && value) return value
  return undefined
}

// The Quartz build mirrors .wikicommit/entity/<lang>/<Type>/<slug>.md 1:1
// into content/<lang>/<Type>/<slug>.md (see scripts/convert_wikilinks.py), so
// a stored repo-root-relative page path maps to a Quartz relativePath by
// dropping the .wikicommit/entity/ prefix. Used for `translated_from` and for
// each `derived_from[].path` (Issue #587) — both store the same path form, so
// both get the same backward compatibility below rather than a second copy of
// it that could drift. Matching must use relativePath (the path
// relative to the content root, set from vfile.data.relativePath), not slug
// or filePath: Quartz lowercases slug (e.g. "ja/person/yamada-taro") but
// relativePath preserves the original path casing (e.g.
// "ja/Person/yamada-taro.md") like translated_from does, while filePath on
// component props is the absolute filesystem path of the source file.
// Tolerates a leading "./" and surrounding whitespace before stripping the
// entity-root prefix (Issue #378): translated_from only has to point at a
// file that exists on disk to pass validate_frontmatter.py, so a
// hand-authored page (written by a human rather than by wikicommit-generate) can use
// either of these variants and still pass CI, but the exact-prefix match
// below previously only recognized the canonical form and silently fell
// through to an unresolved parent (no crash — resolveSources() already
// handles a nonexistent parent — but a missing sources box on the
// translation page). Also strips the pre-Issue-#477 `.wikicommit/wiki/`
// prefix — a translation page written before that rename keeps its old
// translated_from verbatim (no auto-migration; the old and new forms are
// allowed to coexist).
function entityPathToRelativePath(entityPath: string): string {
  return entityPath
    .trim()
    .replace(/^\.\//, "")
    .replace(/^\.wikicommit\/(entity|wiki)\//, "")
    // Drop a custom type's `custom/` segment: convert_wikilinks.py publishes
    // .wikicommit/entity/<lang>/custom/<Type>/<slug>.md to
    // content/<lang>/<Type>/<slug>.md (Issue #576), and `relativePath` is
    // content-relative. Without this the lookup below finds nothing for a
    // translated custom-type page — silently, since a miss is indistinguishable
    // from "no parent page", so source inheritance and the original-page link
    // would just stop working rather than error.
    .replace(/^([^/]+)\/custom\//, "$1/")
}

function resolveDerivations(
  currentSlug: FullSlug,
  entries: DerivedEntry[],
  allFiles: QuartzComponentProps["allFiles"],
): ResolvedDerivation[] {
  const resolved: ResolvedDerivation[] = []
  for (const entry of entries) {
    const path = entry?.path
    if (typeof path !== "string" || path.trim() === "") continue
    const relativePath = entityPathToRelativePath(path)
    const page = allFiles.find((f) => f.relativePath === relativePath)
    if (!page || page.frontmatter?.status === "removed") {
      resolved.push({ label: relativePath, unavailable: true })
      continue
    }
    resolved.push({
      label: (page.frontmatter?.title as string | undefined) ?? relativePath,
      href: page.slug ? resolveRelative(currentSlug, page.slug as FullSlug) : undefined,
      unavailable: false,
    })
  }
  return resolved
}

// Historical note (Issue #212): this used to be kept in sync by hand with a
// resolve_page_sources() function in .wikicommit/scripts/convert_wikilinks.py,
// which built the old content/<lang>/sources.md aggregation page from the
// same own-or-inherited-via-translated_from rule. Issue #476 replaced that
// aggregation with a content/sources/ tree built directly from
// .wikicommit/source/ management files (not from pages' own `sources`
// frontmatter), so resolve_page_sources() no longer exists in Python —
// this per-page inline sources box is unaffected and keeps its own
// standalone inheritance logic below.

// A fresh object each time rather than one shared constant: the arrays would
// otherwise be the same two instances on every no-provenance page.
function emptyProvenance(): ResolvedProvenance {
  return { sources: [], derivations: [], inherited: false }
}

function resolveProvenance(
  currentSlug: FullSlug,
  frontmatter: Record<string, unknown> | undefined,
  allFiles: QuartzComponentProps["allFiles"],
): ResolvedProvenance {
  const ownSources = asSourceList(frontmatter?.sources)
  const ownDerivations = resolveDerivations(
    currentSlug,
    asDerivedList(frontmatter?.derived_from),
    allFiles,
  )
  if (ownSources.length > 0 || ownDerivations.length > 0) {
    return { sources: ownSources, derivations: ownDerivations, inherited: false }
  }

  const translatedFrom = frontmatter?.translated_from
  if (typeof translatedFrom !== "string" || translatedFrom.length === 0) {
    return emptyProvenance()
  }

  const parentRelativePath = entityPathToRelativePath(translatedFrom)
  const parent = allFiles.find((f) => f.relativePath === parentRelativePath)
  if (parent?.frontmatter?.status === "removed") return emptyProvenance()
  const parentSources = asSourceList(parent?.frontmatter?.sources)
  // A translation of a synthesized page carries `translated_from`, and its
  // parent's provenance lives in `derived_from` rather than `sources` — so
  // inheritance has to cover both, or the translation shows nothing for
  // exactly the reason Issue #587 was filed about the original.
  const parentDerivations = resolveDerivations(
    currentSlug,
    asDerivedList(parent?.frontmatter?.derived_from),
    allFiles,
  )
  if (parentSources.length === 0 && parentDerivations.length === 0) return emptyProvenance()

  return {
    sources: parentSources,
    derivations: parentDerivations,
    inherited: true,
    parentTitle: (parent?.frontmatter?.title as string | undefined) ?? parentRelativePath,
    parentHref: parent?.slug
      ? resolveRelative(currentSlug, parent.slug as FullSlug)
      : undefined,
  }
}

// Kept in sync by hand with path_href() in
// .wikicommit/scripts/convert_wikilinks.py (Issue #212), including the
// `main` branch assumption. See resolveSources() above for why this can't
// be a shared function.
function pathHref(path: string): string | undefined {
  const repo = process.env.GITHUB_REPOSITORY
  if (!repo) return undefined
  return `https://github.com/${repo}/blob/main/${path
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`
}

function renderSource(source: SourceEntry, index: number, t: ReturnType<typeof i18n>["components"]["wikicommitSources"]) {
  switch (source.type) {
    case "path": {
      if (typeof source.path !== "string" || !source.path) return null
      const href = pathHref(source.path)
      return (
        <li key={index} class="wikicommit-sources__item">
          {href ? (
            <a href={href} class="wikicommit-sources__link" target="_blank" rel="noopener noreferrer">
              {source.path}
            </a>
          ) : (
            <span class="wikicommit-sources__text">{source.path}</span>
          )}
          {renderLicense(source.license)}
        </li>
      )
    }
    case "url":
    case "wikicommit": {
      if (typeof source.url !== "string" || !source.url) return null
      return (
        <li key={index} class="wikicommit-sources__item">
          <a href={source.url} class="wikicommit-sources__link" target="_blank" rel="noopener noreferrer">
            {source.url}
          </a>
          {renderLicense(source.license)}
        </li>
      )
    }
    case "manual": {
      const author = source.author ?? t.unknownAuthor
      const createdAt = formatDate(source.created_at)
      return (
        <li key={index} class="wikicommit-sources__item">
          <span class="wikicommit-sources__text">
            {t.addedBy} {author}
            {createdAt ? ` (${createdAt})` : ""}
          </span>
          {renderLicense(source.license)}
        </li>
      )
    }
    default:
      return null
  }
}

const WikiCommitSources: QuartzComponent = ({ fileData, allFiles, cfg }: QuartzComponentProps) => {
  const frontmatter = fileData.frontmatter
  if (frontmatter?.status === "removed") return null
  const currentSlug = fileData.slug as FullSlug
  const { sources, derivations, inherited, parentTitle, parentHref } = resolveProvenance(
    currentSlug,
    frontmatter,
    allFiles,
  )

  if (sources.length === 0 && derivations.length === 0) return null

  const t = i18n(resolveLocale(frontmatter?.lang, cfg?.locale)).components.wikicommitSources
  const items = sources
    .map((source, index) => renderSource(source, index, t))
    .filter((item) => item !== null)

  if (items.length === 0 && derivations.length === 0) return null

  // Every page WikiCommit *generates* is an LLM summary/restructuring of its
  // sources, never a verbatim reproduction, so the "indicate if you modified
  // the material" requirement common to CC BY/BY-SA holds for all of them
  // alike and needs no per-page bookkeeping (Issue #558). A `type: manual`
  // entry is the one case where that is not what happened: it records a human
  // who wrote the page directly, so a page whose
  // sources are all manual would be publishing a false authorship statement.
  // Such a page still gets the scope disclaimer whenever a license is on
  // display, since that half is about which material the license covers, not
  // about how the page was written.
  const adapted = sources.some((source) => source.type !== "manual")
  const showsALicense = sources.some(
    (source) => typeof source.license === "string" && source.license.trim() !== "",
  )
  const notice = adapted
    ? t.adaptationNotice
    : showsALicense
      ? t.licenseScopeNotice
      : undefined

  return (
    <div class="wikicommit-sources">
      <h3 class="wikicommit-sources__title">{t.title}</h3>
      {inherited && (
        <p class="wikicommit-sources__inherited">
          {t.inheritedFrom}{" "}
          {parentHref ? <a href={parentHref}>{parentTitle}</a> : parentTitle}
        </p>
      )}
      {items.length > 0 && <ul class="wikicommit-sources__list">{items}</ul>}
      {derivations.length > 0 && (
        <>
          <p class="wikicommit-sources__derived">{t.derivedFrom}</p>
          <ul class="wikicommit-sources__list">
            {derivations.map((derivation, index) => (
              <li key={index} class="wikicommit-sources__item">
                {derivation.href ? (
                  <a href={derivation.href} class="wikicommit-sources__link">
                    {derivation.label}
                  </a>
                ) : (
                  <span class="wikicommit-sources__text">{derivation.label}</span>
                )}
                {derivation.unavailable && (
                  <span class="wikicommit-sources__unavailable"> ({t.unavailablePage})</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
      {notice && <p class="wikicommit-sources__notice">{notice}</p>}
    </div>
  )
}

WikiCommitSources.css = style

export default (() => WikiCommitSources) satisfies QuartzComponentConstructor
