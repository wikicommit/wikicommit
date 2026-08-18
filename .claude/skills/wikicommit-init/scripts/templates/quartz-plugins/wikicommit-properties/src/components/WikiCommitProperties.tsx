import type {
  QuartzComponent,
  QuartzComponentProps,
  QuartzComponentConstructor,
} from "@quartz-community/types"
import { classNames } from "../util/lang"
import { resolveRelative, slugifyWikilinkTarget } from "../util/path"
import { i18n, resolveLocale } from "../i18n"
import style from "./styles/wikicommit-properties.scss"
// @ts-expect-error - inline script import handled by Quartz bundler
import script from "./scripts/wikicommitProperties.inline.ts"

export interface WikiCommitPropertiesComponentOptions {
  collapsed?: boolean
}

const WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g
const MDLINK_RE = /\[([^\]]*)\]\(([^)]+)\)/g
const URL_RE = /https?:\/\/[^\s<>]+/g
// Sentence-final punctuation immediately following a bare URL (e.g.
// "https://example.com/page." at the end of a sentence, upstream-inherited
// bug #2 in Issue #514) is not part of the URL, but URL_RE's [^\s<>]+ has no
// way to know that — it only stops at whitespace/angle-brackets, so it
// swallows trailing punctuation into the link and produces a broken href.
// Deliberately excludes straight ASCII quote/apostrophe ('/"): unlike the
// other characters here, those can legitimately be a URL's own final
// character (e.g. a query string like "?q=don't"), so trimming them
// unconditionally would corrupt a working link instead of fixing a broken
// one — under-trimming is the safer failure mode. Includes typographic
// "smart" punctuation (curly quotes, ellipsis) alongside the ASCII/CJK set:
// WikiCommit's wiki pages are LLM-generated (CLAUDE.md) and LLMs commonly
// emit these instead of straight ASCII forms, and — unlike straight
// quotes — a literal URL essentially never legitimately ends in one.
// The character class below includes, after the ASCII/CJK punctuation:
// U+2026 ellipsis, U+2018/U+2019 left/right single quote, U+201C/U+201D
// left/right double quote.
const TRAILING_PUNCTUATION_RE = /[.,;:!?。、！？…‘’“”]+$/

// Trims a trailing ")" only when it has no matching "(" earlier in the same
// URL (e.g. a bare URL wrapped in prose parentheses, "(see
// https://example.com/page)" — a pattern common enough in Markdown prose
// that TRAILING_PUNCTUATION_RE's deliberate exclusion of closing brackets
// would otherwise leave broken). A URL that legitimately ends in a
// balanced paren (e.g. a Wikipedia article title, ".../wiki/Foo_(bar)") is
// left untouched, since its ")" does have a matching "(" within the URL.
function trimUnbalancedTrailingParen(url: string): string {
  while (url.endsWith(")")) {
    const opens = (url.match(/\(/g) ?? []).length
    const closes = (url.match(/\)/g) ?? []).length
    if (closes <= opens) break
    url = url.slice(0, -1)
  }
  return url
}

type RenderCtx = { slug: string; resolvedLinks: Record<string, string> }

function lookupHref(ctx: RenderCtx, slugifiedTarget: string): string {
  return ctx.resolvedLinks[slugifiedTarget] ?? resolveRelative(ctx.slug, slugifiedTarget)
}

function renderTextWithLinks(text: string, ctx: RenderCtx): (preact.JSX.Element | string)[] {
  const segments: { start: number; end: number; node: preact.JSX.Element }[] = []
  for (const match of text.matchAll(WIKILINK_RE)) {
    const target = match[1]!
    const display = match[2] ?? target
    const href = lookupHref(ctx, slugifyWikilinkTarget(target))
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: (
        <a href={href} class="internal internal-link wikicommit-properties-link">
          {display}
        </a>
      ),
    })
  }

  for (const match of text.matchAll(MDLINK_RE)) {
    const overlaps = segments.some(
      (s) => match.index < s.end && match.index + match[0].length > s.start,
    )
    if (overlaps) continue
    const display = match[1]!
    const href = match[2]!
    const isExternal = href.startsWith("http://") || href.startsWith("https://")
    const resolvedHref = isExternal ? href : lookupHref(ctx, href)
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: (
        <a
          href={resolvedHref}
          class={classNames(
            isExternal ? "external external-link" : "internal internal-link",
            "wikicommit-properties-link",
          )}
          {...(isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        >
          {display || href}
        </a>
      ),
    })
  }

  for (const match of text.matchAll(URL_RE)) {
    const overlaps = segments.some(
      (s) => match.index < s.end && match.index + match[0].length > s.start,
    )
    if (overlaps) continue

    const url = trimUnbalancedTrailingParen(match[0].replace(TRAILING_PUNCTUATION_RE, ""))
    // A degenerate match trimmed down to just the bare scheme (e.g. source
    // text like "https://...." matches URL_RE, then TRAILING_PUNCTUATION_RE
    // strips every character after the scheme) has no host and isn't a
    // real link — `url.length === 0` alone can't catch this, since
    // "https://" itself is 8 non-punctuation characters.
    if (url.replace(/^https?:\/\//, "").length === 0) continue

    segments.push({
      start: match.index,
      end: match.index + url.length,
      node: (
        <a
          href={url}
          class="external external-link wikicommit-properties-link"
          target="_blank"
          rel="noopener noreferrer"
        >
          {url}
        </a>
      ),
    })
  }

  if (segments.length === 0) return [text]

  segments.sort((a, b) => a.start - b.start)

  const result: (preact.JSX.Element | string)[] = []
  let cursor = 0
  for (const seg of segments) {
    if (seg.start > cursor) {
      result.push(text.slice(cursor, seg.start))
    }
    result.push(seg.node)
    cursor = seg.end
  }
  if (cursor < text.length) {
    result.push(text.slice(cursor))
  }

  return result
}

function renderValue(value: unknown, ctx: RenderCtx): preact.JSX.Element | string {
  if (value === null || value === undefined) {
    return <span class="wikicommit-properties-empty">—</span>
  }

  if (typeof value === "boolean") {
    return (
      <span class={classNames("wikicommit-properties-boolean", value ? "is-true" : "is-false")}>
        <input type="checkbox" checked={value} disabled />
      </span>
    )
  }

  if (typeof value === "number") {
    return <span class="wikicommit-properties-number">{value}</span>
  }

  if (typeof value === "string") {
    const parts = renderTextWithLinks(value, ctx)
    return <span class="wikicommit-properties-text">{parts}</span>
  }

  if (Array.isArray(value)) {
    const items = value.map((item, idx) => {
      const rendered = renderValue(item, ctx)
      return (
        <>
          {idx > 0 && <span class="wikicommit-properties-separator">, </span>}
          {rendered}
        </>
      )
    })
    return <span class="wikicommit-properties-list">{items}</span>
  }

  // WikiCommit's own nested `properties:` block is flattened one level before
  // it ever reaches this function (see getVisibleProperties() in
  // transformer.ts, Issue #509), so a plain object only lands here if a
  // *different* frontmatter field happens to hold one — unchanged from
  // upstream, which renders that case as a raw JSON dump.
  if (typeof value === "object") {
    return (
      <span class="wikicommit-properties-object">
        <code>{JSON.stringify(value)}</code>
      </span>
    )
  }

  return String(value)
}

function renderTagList(tags: string[], ctx: RenderCtx): preact.JSX.Element {
  const items = tags.map((tag, idx) => {
    const href = resolveRelative(ctx.slug, `tags/${tag}`)
    return (
      <>
        {idx > 0 && <span class="wikicommit-properties-separator">, </span>}
        <a href={href} class="internal internal-link tag-link">
          {tag}
        </a>
      </>
    )
  })
  return <span class="wikicommit-properties-tags">{items}</span>
}

export default ((opts?: WikiCommitPropertiesComponentOptions) => {
  const { collapsed = false } = opts ?? {}

  const Component: QuartzComponent = (props: QuartzComponentProps) => {
    const wcProps = props.fileData?.wikicommitProperties as
      | {
          properties: Record<string, unknown>
          hideView: boolean
          showProperties?: boolean
          collapseProperties?: boolean
          resolvedLinks?: Record<string, string>
        }
      | undefined
    if (!wcProps) return null

    // Per-note override takes precedence over global config
    // showProperties: true = force show, false = force hide, undefined = follow hideView config
    if (wcProps.showProperties === false) return null
    if (wcProps.showProperties !== true && wcProps.hideView) return null

    const properties = wcProps.properties
    const entries = Object.entries(properties)
    if (entries.length === 0) return null

    const frontmatter = props.fileData?.frontmatter as Record<string, unknown> | undefined
    const t = i18n(resolveLocale(frontmatter?.lang, props.cfg?.locale)).components
      .wikicommitProperties
    const ctx: RenderCtx = {
      slug: (props.fileData?.slug as string) ?? "",
      resolvedLinks: wcProps.resolvedLinks ?? {},
    }

    // Per-note collapse override takes precedence over component option
    const isCollapsed = wcProps.collapseProperties ?? collapsed
    return (
      <details
        class={classNames(props.displayClass, "wikicommit-properties", "metadata-container")}
        open={!isCollapsed}
        data-collapsed={isCollapsed}
      >
        <summary class="wikicommit-properties-header">
          <span class="wikicommit-properties-title">{t.title}</span>
          <span class="wikicommit-properties-count">{entries.length}</span>
        </summary>
        <table class="wikicommit-properties-table">
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key} class="wikicommit-properties-row metadata-property">
                <td class="wikicommit-properties-key metadata-property-key">{key}</td>
                <td class="wikicommit-properties-value metadata-property-value">
                  {key === "tags" && Array.isArray(value)
                    ? renderTagList(value as string[], ctx)
                    : renderValue(value, ctx)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    )
  }

  Component.css = style
  Component.afterDOMLoaded = script

  return Component
}) satisfies QuartzComponentConstructor
