import type {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "@quartz-community/types"
import { i18n, resolveLocale } from "../i18n"
import style from "./styles/wikicommit-banner.scss"

// Kept in sync by hand with the identically-named function in
// WikiCommitSources.tsx (Issue #528) — each quartz-plugins/ package builds
// independently (its own package.json/dist), so this small pure function is
// duplicated rather than imported across packages. See WikiCommitSources.tsx's
// comment on this function for the full rationale (relativePath vs. slug vs.
// filePath, the leading "./" and pre-Issue-#477 ".wikicommit/wiki/" prefix
// tolerance). Named for the transformation rather than for `translated_from`
// because the Sources copy now runs it over `derived_from[].path` too (Issue
// #587); this copy still only has `translated_from` to feed it, and the shared
// name is what keeps the two findable as a pair.
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

  const parentRelativePath = entityPathToRelativePath(translatedFrom)
  const parent = allFiles.find((f) => f.relativePath === parentRelativePath)
  if (parent?.frontmatter?.status === "removed") return translatedFrom

  return buildPageUrl(cfg?.baseUrl, parent?.slug as string | undefined) ?? translatedFrom
}

// Shared by the report link (aria-describedby) and its account note (id).
const REPORT_NOTE_ID = "wikicommit-banner-report-note"

// Stamped onto content/ only, by convert_wikilinks.py (Issue #751). Kept as
// named constants because the two spellings have to match that script's
// AI_REVIEW_AT_FIELD / AI_REVIEW_MODEL_FIELD exactly, and a typo would fail
// silently — the line would just never appear.
const AI_REVIEW_AT_FIELD = "ai_review_at"
const AI_REVIEW_MODEL_FIELD = "ai_review_model"

// A page's review tracking Issue (Issue #313) is created by wikicommit-merge
// Step 8 *after* the PR merges, while the Quartz build runs off that same
// merge — so at build time the Issue number does not exist yet, and it is not
// stored in frontmatter either. What can be assembled statically is the Issue
// title `Review: <Type>/<slug> (<lang>)` and the label `wikicommit-review`,
// which is enough for a GitHub Issue *search* URL (Issue #579).
//
// Three deliberate properties of the query:
//
//   - It searches `<Type>/<slug> (<lang>)`, never the page's `title`
//     frontmatter. The Issue title does not contain the page title, and a
//     regeneration can change that title while type/slug/lang stay fixed
//     (regeneration is page-scoped, so it takes both as given) — keying on the
//     title would make the link go stale on every regeneration.
//   - The `Review:` prefix is left out. It carries no discriminating power
//     (`label:wikicommit-review` already restricts the set, and every such
//     Issue starts with it) and it is the only colon in the phrase, so
//     dropping it removes the one part whose behaviour inside a quoted search
//     phrase would be worth arguing about.
//   - `is:open` matters most. A regenerated page returns to `pending` and gets
//     a *new* tracking Issue, so one page can accumulate several same-titled
//     Issues over time; without the filter the link could offer an
//     already-closed Issue as the current place to review, which is worse than
//     offering nothing. `is:open` is used rather than `state:open` because it
//     is the form GitHub's own issue list emits (`?q=is%3Aissue+is%3Aopen`).
//
// GitHub matches title text by token, so a search can also surface a
// neighbouring page whose slug extends this one (`.../yamada-taro` alongside
// `.../yamada-taro-jr`). That is accepted: the link lands on a filtered search
// results page rather than claiming to open one specific Issue, and the label
// and state filters keep the list short. It is also why the link text does not
// promise a particular Issue.
function buildReviewSearchUrl(
  repo: string | undefined,
  type: string | undefined,
  lang: string | undefined,
  relativePath: string | undefined,
): string | undefined {
  // Anything missing means the search key cannot be built, so no link is
  // rendered at all — better than a link that is guaranteed to find nothing.
  // This also keeps the link off the folder and tag pages Quartz generates
  // itself, which have no frontmatter (and therefore no type/lang) and no
  // tracking Issue to find.
  if (!repo || !type || !lang || !relativePath) return undefined
  const slug = relativePath.split("/").pop()?.replace(/\.md$/, "")
  if (!slug) return undefined
  const q = `is:issue is:open label:wikicommit-review in:title "${type}/${slug} (${lang})"`
  return `https://github.com/${repo}/issues?q=${encodeURIComponent(q)}`
}

/**
 * Render `readBy` — a sentence carrying a `{name}` placeholder — with the
 * reviewer's GitHub profile link in the placeholder's position (Issue #800).
 *
 * The line used to be a bare `label: value` pair, so a plain label plus a link
 * was enough. It now states what the reading found as well as who did it, and
 * word order differs per language (Japanese puts the name first, English last),
 * so the whole sentence lives in the locale string and only the link is
 * substituted here. `counts` in convert_wikilinks.py already carries
 * placeholders this way; this is not a new pattern in the project.
 *
 * A locale string that somehow lacks `{name}` still renders: the split yields
 * one part, the link is appended after it, and nothing is dropped.
 */
function renderReadBy(template: string, login: string) {
  const [before, ...rest] = template.split("{name}")
  const after = rest.join("{name}")
  return (
    <>
      {before}
      <a href={`https://github.com/${encodeURIComponent(login)}`}>{login}</a>
      {after}
    </>
  )
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

  // Site-wide summary (total page count, reviewed count): convert_wikilinks.py's
  // generate_root_index() embeds these as frontmatter on the build-generated
  // content/index.md only (Issue #407). Gating on field presence rather than on
  // fileData.slug === "index" avoids coupling this component to Quartz's slug naming
  // convention for the root page.
  //
  // A `wikicommit_theme` line was rendered here until Issue #670. config.yml's
  // `theme` is an LLM-facing scope instruction, not reader-facing copy: it is a
  // single string in one language, so on a multilingual wiki it was unreadable
  // for most readers, and it often carried source-selection prose written for
  // the generator.
  const pageCount = frontmatter?.wikicommit_page_count as number | undefined
  const reviewedCount = frontmatter?.wikicommit_reviewed_count as number | undefined
  // Issue #769: written only when at least one page carries a standing verdict,
  // so its absence is "no record" rather than "nothing was checked" — a wiki
  // generated before review records existed has none, and they are not created
  // retroactively. Guarded on the type, like the two counts above, because a
  // stale content/index.md from an earlier build could carry anything.
  const aiReviewedCount = frontmatter?.wikicommit_ai_reviewed_count as number | undefined
  const siteSummary =
    typeof pageCount === "number" && typeof reviewedCount === "number" ? (
      <div class="wikicommit-site-summary">
        <p class="wikicommit-site-summary__counts">
          {t.siteSummaryPages} <strong>{pageCount}</strong>
          &nbsp;&nbsp;
          {/* The full-coverage number first, then the sample taken out of it —
              the same order the overview page uses. */}
          {typeof aiReviewedCount === "number" ? (
            <>
              {t.siteSummaryAiReviewed} <strong>{aiReviewedCount}</strong>
              &nbsp;&nbsp;
            </>
          ) : null}
          {t.siteSummaryReviewed} <strong>{reviewedCount}</strong>
        </p>
        {/* Issue #664: the count alone reads as "nobody cares about this
            project" to a first-time reader — the opposite of the honesty it was
            added for. The number stays (hiding it would give that up) and this
            line says what it counts: pages go live the moment they are
            generated, so this is how many have since been read by a person,
            not how far along the wiki is. Deliberately not an invitation to
            review — this wiki does not take outside reviewers. */}
        <p class="wikicommit-site-summary__note">{t.siteSummaryReviewNote}</p>
        {/* Issue #769: a separate note, shown only with the count it explains.
            Its wording names what the check does *not* cover — stating only
            what it does would rebuild, facing the other way, the overstatement
            Issue #740 removed from "read by a person". */}
        {typeof aiReviewedCount === "number" ? (
          <p class="wikicommit-site-summary__note">{t.siteSummaryAiReviewNote}</p>
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

  // Issue #751: written onto the published copy by convert_wikilinks.py, which
  // reads .wikicommit/review/ at build time. No page in .wikicommit/entity/
  // carries these, so nothing here needs a validate_frontmatter.py rule.
  //
  // Absent for three reasons that must all render exactly as this banner
  // rendered before the feature existed: the page predates the record tree
  // (Issue #750 — records cannot be made retroactively), the verdict went stale
  // when /wikicommit-fix rewrote the page, or the record would not parse.
  // Publishing decides which of those it is; here the field is simply missing.
  //
  // Shown in both states for the reason Issue #739 collapsed the two branches
  // into one: passing the source check is a fact about how the page was made,
  // and a person later reading the page neither adds to it nor takes it away.
  const aiReviewAt = frontmatter?.[AI_REVIEW_AT_FIELD]
  const aiReviewBy = frontmatter?.[AI_REVIEW_MODEL_FIELD]
  const aiReviewLine =
    typeof aiReviewAt === "string" &&
    aiReviewAt.trim() !== "" &&
    typeof aiReviewBy === "string" &&
    aiReviewBy.trim() !== "" ? (
      <p class="wikicommit-banner__ai-review">
        {t.aiReviewAt} {aiReviewAt}&nbsp;&nbsp;{t.aiReviewBy} {aiReviewBy}
      </p>
    ) : null

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
  // The page facts, then what this wiki is actually asking readers to look for
  // (Issue #738). The guidance is built from i18n strings rather than written
  // into .github/ISSUE_TEMPLATE/report.md so it follows the page's own
  // language — report.md is a single file with no language of its own, and a
  // Japanese reader reaching it through this link would otherwise get English
  // prompts. report.md carries a short version for whoever opens it directly.
  //
  // Deliberately not a checklist and not on the banner itself: `- [ ]` is an
  // attestation UI, and putting these lines in the banner would show the same
  // two prompts on every page on every visit, which is how a standing notice
  // stops being read (the reason Issue #562 demoted the low-density guard).
  // Here they appear only once someone has already decided to report.
  const reportFacts = [
    pageUrl ? `${t.reportBodyPage} ${pageUrl}` : null,
    lang ? `${t.reportBodyLanguage} ${lang}` : null,
    originalPageInfo ? `${t.reportBodyOriginal} ${originalPageInfo}` : null,
  ].filter((line): line is string => line !== null)
  //
  // Wrapped in an HTML comment, the way every prompt in
  // .github/ISSUE_TEMPLATE/report.md is. That file's prompts disappear when the
  // Issue is submitted; a `body=` prefill is ordinary text and would not, so
  // these lines would be posted as part of the report itself. That matters
  // beyond tidiness: `/wikicommit-fix` treats an Issue's whole body as the
  // feedback and classifies "each distinct point" in it, so three standing
  // bullets left in every report become three points it tries to act on.
  const reportGuidance = [
    t.reportBodyProblemHeading,
    "",
    "<!--",
    t.reportBodyGuidanceHeading,
    "",
    t.reportBodyGuidanceHarm,
    t.reportBodyGuidanceKnowledge,
    t.reportBodyGuidanceContradiction,
    "",
    t.reportBodyGuidanceFooter,
    "-->",
    "",
  ]
  // The blank separator belongs to the facts, not to the guidance: a page with
  // no resolvable URL, language or original would otherwise open its Issue on
  // an empty first line.
  const reportBody = [...reportFacts, ...(reportFacts.length ? [""] : []), ...reportGuidance].join(
    "\n",
  )

  const reportUrl = repo
    ? `https://github.com/${repo}/issues/new?template=report.md&title=${encodeURIComponent(reportTitle)}${
        reportBody ? `&body=${encodeURIComponent(reportBody)}` : ""
      }`
    : "#"

  // Built once and used by both branches below, the way `siteSummary` is: the
  // two report rows render an identical link + note pair, and keeping one copy
  // stops them drifting apart the next time either is touched.
  //
  // `aria-describedby` ties the note to the link it annotates. Without it a
  // reader moving through the page by its link list — one of the groups this
  // note exists for — hears only the label and still lands on the login wall
  // unannounced. The banner renders once per page, so the id is unique.
  const reportAction = (
    <span class="wikicommit-banner__report-action">
      <a href={reportUrl} class="wikicommit-banner__link" aria-describedby={REPORT_NOTE_ID}>
        {t.reportLink}
      </a>
      <span class="wikicommit-banner__link-note" id={REPORT_NOTE_ID}>
        {t.reportLinkAccountNote}
      </span>
    </span>
  )

  // Who the `reviewed` state belongs to (Issue #663). review-issue-close-sync.yml
  // writes this login into frontmatter in the same commit that flips
  // review_status, so the value is here for the same reason generated_by is —
  // this component reads frontmatter and nothing else. Absent on any page
  // reviewed before that field existed, and on every page in a wiki that does
  // not run the workflow, so it is rendered only when present: without it the
  // reviewed branch falls back to exactly the markup it had before, rather than
  // showing an empty label or the "unknown" placeholder the pending branch uses
  // for generated_at/generated_by. Those two differ on purpose — a generated
  // page always went through generation, so a missing value there is a gap worth
  // naming, whereas a missing reviewer is the normal state of a page reviewed
  // any other way.
  const reviewedBy =
    typeof frontmatter?.reviewed_by === "string" && frontmatter.reviewed_by.trim() !== ""
      ? frontmatter.reviewed_by.trim()
      : undefined

  // Does this page record having been generated at all (Issue #739)? Both
  // states now state that the page is LLM-written, so this has to be decided
  // from the frontmatter rather than from `review_status`, for one specific
  // reason: `review_status: reviewed` is also what rebuild_index.py stamps on
  // build-generated index pages, precisely so this banner stays quiet on them
  // (Issue #580). Those pages are not LLM-written and carry no generation
  // stamp, so keying on the stamp keeps them exactly as they were instead of
  // telling a reader the site's own front page was written by a model.
  //
  // A pending page is exempt from the check and keeps the "unknown"
  // placeholders it has always shown: only wikicommit-generate / -translate /
  // -synthesize ever write `pending`, so such a page went through generation
  // by construction and a missing stamp there is a gap worth naming, not an
  // open question (the same asymmetry Issue #663 records for reviewed_by).
  //
  // The fields checked are exactly the pair the banner will render, which is
  // why isTranslation selects them rather than the union of all four being
  // checked. A translation page only ever displays translated_at/translated_by
  // (the labels switch with it, above), so letting generated_at/generated_by
  // open the gate for one would render the reviewed banner with
  // "Translated: unknown  Model: unknown" — a generation notice carrying no
  // generation data, which is the very outcome this gate exists to keep off
  // stamp-less reviewed pages. The same holds mirrored for an ordinary page
  // that somehow carries only translated_*.
  const stampFields = isTranslation
    ? (["translated_at", "translated_by"] as const)
    : (["generated_at", "generated_by"] as const)
  const hasGenerationStamp = stampFields.some(
    (field) => typeof frontmatter?.[field] === "string" && (frontmatter[field] as string).trim() !== "",
  )

  if (!isPending && !hasGenerationStamp) {
    return (
      <>
        {siteSummary}
        <div class="wikicommit-banner__report">
          {reviewedBy ? (
            <span class="wikicommit-banner__reviewer">
              {renderReadBy(t.readBy, reviewedBy)}
            </span>
          ) : null}
          {reportAction}
        </div>
      </>
    )
  }

  // Only on a pending page: while a page is pending its tracking Issue is
  // open, and closing that Issue is what flips the page to reviewed and
  // rebuilds the site (review-issue-close-sync.yml), so the banner carrying
  // this link and the Issue being open begin and end together. A reviewed
  // page's tracking Issue is closed and not worth pointing at; the report
  // link already covers reporting an error there (Issue #245).
  const reviewSearchUrl = isPending
    ? buildReviewSearchUrl(repo, type, lang, fileData.relativePath as string | undefined)
    : undefined

  // One banner for both states, which is the point of Issue #739. Being
  // LLM-written is a permanent fact about the page — review-issue-close-sync.yml
  // rewrites `review_status` and `reviewed_by` and nothing else — so it used to
  // be the case that the moment someone closed a tracking Issue, the only place
  // that fact was stated disappeared. Reviewing does not make a page stop being
  // generated, and a banner that vanishes reads as "a person looked, so the
  // warning no longer applies" — a guarantee `reviewed` does not carry
  // (Issue #723's transition table; Issue #722 on completeness).
  //
  // So review adds a line rather than removing the warning, and the markup says
  // that: same heading, same body, same generation line, plus one line saying a
  // person has read it.
  //
  // Issue #774 finished this. The heading used to swap
  // (`isPending ? t.title : t.titleReviewed`), and a heading that swaps forces
  // the pending side to say *something* — the only thing left to say there was
  // "nobody has read this page yet", which is false in front of the person
  // reading it. It now states a fact true in either state, and the ⚠️ goes with
  // it: being LLM-written is exactly what the icon cautions about, and that does
  // not end at review. The two states are told apart by border colour and by the
  // presence of the read line, neither of which depends on `reviewed_by` being
  // set — a route B page has no login to record.
  return (
    <>
      {siteSummary}
      <div
        class={`wikicommit-banner ${
          isPending ? "wikicommit-banner--pending" : "wikicommit-banner--reviewed"
        }`}
      >
        <span class="wikicommit-banner__icon">⚠️</span>
        <div class="wikicommit-banner__body">
          <strong>{t.title}</strong>
          <p>{t.body}</p>
          <p>
            {generatedAtLabel} {generatedAt}&nbsp;&nbsp;{generatedByLabel} {generatedBy}
          </p>
          {aiReviewLine}
          {/* The line review adds. Rendered for every reviewed page, named or
              not: with the heading no longer swapping, this is what tells the
              two states apart, so it must not depend on `reviewed_by` (absent
              on route B pages and on anything reviewed before Issue #663).
              With a name the `readBy` line states what the reading found and who
              did it; without one the fallback states the same finding unnamed,
              rather than an empty label or an `unknown` placeholder — a missing
              reviewer is a normal state, not a gap to fill (Issue #663). */}
          {!isPending ? (
            <p class="wikicommit-banner__reviewer">
              {reviewedBy ? (
                renderReadBy(t.readBy, reviewedBy)
              ) : (
                t.readByAPerson
              )}
            </p>
          ) : null}
          <div class="wikicommit-banner__actions">
            {reviewSearchUrl ? (
              <a href={reviewSearchUrl} class="wikicommit-banner__link">
                {t.reviewStatusLink}
              </a>
            ) : null}
            {reportAction}
          </div>
        </div>
      </div>
    </>
  )
}

WikiCommitBanner.css = style

export default (() => WikiCommitBanner) satisfies QuartzComponentConstructor
