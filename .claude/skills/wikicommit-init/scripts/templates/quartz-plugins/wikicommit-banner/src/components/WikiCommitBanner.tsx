import type {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "@quartz-community/types"
import { i18n, resolveLocale } from "../i18n"
import style from "./styles/wikicommit-banner.scss"

// Kept in sync by hand with the identically-named function in
// WikiCommitSources.tsx (Issue #528, following the same pattern as Issue
// #528's own translatedFromToRelativePath()) — each quartz-plugins/ package
// builds independently (its own package.json/dist), so this small pure
// function is duplicated rather than imported across packages. See
// WikiCommitSources.tsx's comment on this function for the full rationale
// (relativePath vs. slug vs. filePath, the leading "./" and pre-Issue-#477
// ".wikicommit/wiki/" prefix tolerance).
function translatedFromToRelativePath(translatedFrom: string): string {
  return translatedFrom
    .trim()
    .replace(/^\.\//, "")
    .replace(/^\.wikicommit\/(entity|wiki)\//, "")
}

function buildPageUrl(baseUrl: string | undefined, slug: string | undefined): string | undefined {
  return baseUrl && slug ? `https://${baseUrl.replace(/\/+$/, "")}/${slug}` : undefined
}

// Issue #528: isTranslation (below) previously fed only the
// Translated:/Model: label switch, so a reader-filed Issue on a translation
// page carried no signal that the page is a translation or where the
// original lives — a triager had to open the page and read translated_from
// themselves. Resolves the original page's own public URL the same way
// WikiCommitSources.tsx's resolveSources() resolves it for the inline
// sources box (matching allFiles by relativePath, not slug — see that
// file's comment for why), so it doubles as valid input to
// `/wikicommit-fix <published-page-url> "<instruction>"` (Issue #454's
// published-URL-driven route), not just a human-readable pointer. Falls
// back to the raw translated_from path (always present whenever the page
// has translated_from) when a URL can't be resolved — no cfg.baseUrl, no
// matching allFiles entry, or the original page itself is status: removed
// — that raw path is itself directly usable as
// `/wikicommit-fix <page-path> "<instruction>"`'s page-path-driven route
// (a deliberate divergence from resolveSources(), which suppresses entirely
// on a removed parent — that component has nothing useful to show without a
// working link, while this one's raw-path fallback stays actionable even
// then).
function resolveOriginalPageInfo(
  frontmatter: Record<string, unknown> | undefined,
  allFiles: QuartzComponentProps["allFiles"],
  cfg: QuartzComponentProps["cfg"],
): string | undefined {
  const translatedFrom = frontmatter?.translated_from
  if (typeof translatedFrom !== "string") return undefined

  const parentRelativePath = translatedFromToRelativePath(translatedFrom)
  const parent = allFiles.find((f) => f.relativePath === parentRelativePath)
  if (parent?.frontmatter?.status === "removed") return translatedFrom

  return buildPageUrl(cfg?.baseUrl, parent?.slug as string | undefined) ?? translatedFrom
}

const WikiCommitBanner: QuartzComponent = ({ fileData, allFiles, cfg }: QuartzComponentProps) => {
  const frontmatter = fileData.frontmatter
  // WikiCommitSources / WikiCommitJsonLD と同様、removed ページには何も表示しない
  // （報告リンクを常時表示にしたことで、除外しないと存在しないページへのリンクを
  // 出してしまう。Issue #245）。
  if (frontmatter?.status === "removed") return null

  const reviewStatus = (frontmatter?.review_status as string | undefined) ?? "pending"
  const isPending = reviewStatus === "pending"

  const t = i18n(resolveLocale(frontmatter?.lang, cfg?.locale)).components.wikicommitBanner

  // Site-wide summary (total page count, reviewed count, theme): convert_wikilinks.py's
  // generate_root_index() embeds these as frontmatter on the build-generated
  // content/index.md only (Issue #407). Gating on field presence rather than on
  // fileData.slug === "index" avoids coupling this component to Quartz's slug naming
  // convention for the root page.
  const pageCount = frontmatter?.wikicommit_page_count as number | undefined
  const reviewedCount = frontmatter?.wikicommit_reviewed_count as number | undefined
  const theme = frontmatter?.wikicommit_theme as string | undefined
  const siteSummary =
    typeof pageCount === "number" && typeof reviewedCount === "number" ? (
      <div class="wikicommit-site-summary">
        <p class="wikicommit-site-summary__counts">
          {t.siteSummaryPages} <strong>{pageCount}</strong>
          &nbsp;&nbsp;
          {t.siteSummaryReviewed} <strong>{reviewedCount}</strong>
        </p>
        {theme ? (
          <p class="wikicommit-site-summary__theme">
            {t.siteSummaryTheme} {theme}
          </p>
        ) : null}
      </div>
    ) : null

  // Translation pages (translated_from present) carry translated_at/translated_by
  // instead of generated_at/generated_by — a distinct event (when/which model ran
  // /wikicommit-translate) from generation, so they get their own labels rather
  // than reusing the "Generated:"/"Model:" captions for a different underlying
  // value (Issue #453 — translation pages previously had neither the fields nor
  // the display branch, so every translated page's pending banner showed
  // "unknown" for both, unconditionally).
  const isTranslation = typeof frontmatter?.translated_from === "string"
  const generatedAt = isTranslation
    ? ((frontmatter?.translated_at as string | undefined) ?? t.unknown)
    : ((frontmatter?.generated_at as string | undefined) ?? t.unknown)
  const generatedBy = isTranslation
    ? ((frontmatter?.translated_by as string | undefined) ?? t.unknown)
    : ((frontmatter?.generated_by as string | undefined) ?? t.unknown)
  const generatedAtLabel = isTranslation ? t.translatedAt : t.generatedAt
  const generatedByLabel = isTranslation ? t.translatedBy : t.generatedBy

  // Issue報告リンクは reviewed 後もページの誤りを指摘できるよう review_status に
  // 関係なく常時表示する（Issue #245）。後レビュー用 PR の URL は frontmatter に
  // 格納しない（動的に生成しない）。ユーザーが GitHub の PR ページで確認する（Phase 2 スコープ外）。
  const repo = process.env.GITHUB_REPOSITORY
  const title = (frontmatter?.title as string | undefined) ?? ""
  const type =
    typeof frontmatter?.type === "string" ? frontmatter.type.replace(/^schema:/, "") : undefined
  const lang = frontmatter?.lang as string | undefined
  const pageUrl = buildPageUrl(cfg?.baseUrl, fileData.slug)
  const originalPageInfo = isTranslation ? resolveOriginalPageInfo(frontmatter, allFiles, cfg) : undefined

  const reportTitle = type ? `${t.reportTitlePrefix} ${type}: ${title}` : `${t.reportTitlePrefix} ${title}`
  const reportBody = [
    pageUrl ? `${t.reportBodyPage} ${pageUrl}` : null,
    lang ? `${t.reportBodyLanguage} ${lang}` : null,
    originalPageInfo ? `${t.reportBodyOriginal} ${originalPageInfo}` : null,
  ]
    .filter((line): line is string => line !== null)
    .join("\n")

  const reportUrl = repo
    ? `https://github.com/${repo}/issues/new?template=report.md&title=${encodeURIComponent(reportTitle)}${
        reportBody ? `&body=${encodeURIComponent(reportBody)}` : ""
      }`
    : "#"

  if (!isPending) {
    return (
      <>
        {siteSummary}
        <div class="wikicommit-banner__report">
          <a href={reportUrl} class="wikicommit-banner__link">
            {t.reportLink}
          </a>
        </div>
      </>
    )
  }

  return (
    <>
      {siteSummary}
      <div class="wikicommit-banner wikicommit-banner--pending">
        <span class="wikicommit-banner__icon">⚠️</span>
        <div class="wikicommit-banner__body">
          <strong>{t.title}</strong>
          <p>{t.body}</p>
          <p>
            {generatedAtLabel} {generatedAt}&nbsp;&nbsp;{generatedByLabel} {generatedBy}
          </p>
          <div class="wikicommit-banner__actions">
            <a href={reportUrl} class="wikicommit-banner__link">
              {t.reportLink}
            </a>
          </div>
        </div>
      </div>
    </>
  )
}

WikiCommitBanner.css = style

export default (() => WikiCommitBanner) satisfies QuartzComponentConstructor
