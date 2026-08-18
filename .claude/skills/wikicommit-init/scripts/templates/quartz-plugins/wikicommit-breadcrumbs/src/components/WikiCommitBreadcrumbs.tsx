// Fork of github:quartz-community/breadcrumbs's Breadcrumbs.tsx. Neither the
// breadcrumbs nor the explorer plugin offers a YAML-config option to hide a
// path segment (Quartz only exposes filterFn/mapFn-style customization via a
// quartz.ts TypeScript override, which WikiCommit deliberately doesn't use —
// see quartz.config.yaml's own comment on being the sole config surface), so
// this fork exists to drop the .wikicommit/entity/<lang>/ segment that would
// otherwise render as a plain folder level (Issue #196). Kept close to
// upstream to minimize divergence; besides the language-segment removal, the
// two other deltas are the dedicated ctx cache key (see comment below; #210)
// and the removal of the unused `resolveFrontmatterTitle` option (also
// unwired upstream — the vendored fileTrie/ctx trie builder always prefers
// frontmatter title unconditionally, so the option had no effect either way).
import type {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "@quartz-community/types"
import { classNames } from "../util/lang"
import { resolveRelative, simplifySlug } from "../util/path"
import { FileTrieNode, trieFromAllFiles } from "../util/fileTrie"
import style from "./styles/wikicommit-breadcrumbs.scss"

type CrumbData = {
  displayName: string
  path: string
}

export interface BreadcrumbOptions {
  /** Symbol between crumbs */
  spacerSymbol: string
  /** Name of first crumb */
  rootName: string
  /** Whether to display the current page in the breadcrumbs */
  showCurrentPage: boolean
}

const defaultOptions: BreadcrumbOptions = {
  spacerSymbol: "❯",
  rootName: "Home",
  showCurrentPage: true,
}

function formatCrumb(displayName: string, baseSlug: string, currentSlug: string): CrumbData {
  return {
    displayName,
    path: resolveRelative(baseSlug, currentSlug),
  }
}

// .wikicommit/entity/<lang>/<Type>/<slug>.md is mirrored 1:1 into
// content/<lang>/<Type>/<slug>.md (see scripts/convert_wikilinks.py), so the
// node right after the content root (pathNodes[1]) is always the page's
// language directory ("ja", "en", ...), never a meaningful content
// category. WikiCommitLanguageSwitcher is the dedicated UI for actually
// switching languages, so this segment is dropped from the breadcrumb
// trail entirely rather than shown as a clickable folder level. The regex
// guard means a non-lang top-level segment (e.g. this component reused
// outside the .wikicommit/entity/<lang>/ layout) is left untouched instead of
// being silently dropped.
//
// Duplicated (not imported) in wikicommit-language-switcher and
// wikicommit-explorer — the 3 plugins are independent npm packages with no
// shared workspace, so there's no runtime-shareable module between them.
// tests/test_quartz_plugins_lang_segment_sync.py asserts this literal stays
// byte-identical across all 3 copies (Issue #228).
const LANG_SEGMENT_RE = /^[a-z]{2}$/

export default ((opts?: Partial<BreadcrumbOptions>) => {
  const options: BreadcrumbOptions = { ...defaultOptions, ...opts }
  const WikiCommitBreadcrumbs: QuartzComponent = ({
    fileData,
    allFiles,
    displayClass,
    ctx,
  }: QuartzComponentProps) => {
    // Deliberately cached under our own ctx key rather than the core-shared
    // `ctx.trie`. Quartz core's PageTypeDispatcher.emit() sets `ctx.trie` from
    // its own (non-virtual) `allFiles` before any component renders (see
    // `quartz/plugins/pageTypes/dispatcher.ts`), so a `ctx.trie ??= ...` here
    // would always find that value already set and never run. Worse, the
    // component's own `allFiles` prop includes virtual pages (tag-page,
    // folder-page), while core's pre-built `ctx.trie` does not — reusing
    // `ctx.trie` would make ancestryChain() return undefined (hiding the
    // breadcrumb trail entirely) on every tag/folder page. Mirrors the
    // dedicated `wikicommitLanguageIndex` ctx key in the sibling
    // wikicommit-language-switcher plugin for the same reason (Issue #210).
    const typedCtx = (ctx ?? {}) as Record<string, unknown> as {
      wikicommitBreadcrumbsTrie?: FileTrieNode
    }
    typedCtx.wikicommitBreadcrumbsTrie ??= trieFromAllFiles(
      allFiles as Array<{
        slug?: string
        filePath?: string
        frontmatter?: { title?: string; [key: string]: unknown }
      }>,
    )
    const trie = typedCtx.wikicommitBreadcrumbsTrie
    const slug = fileData.slug as string
    const slugParts = slug.split("/")
    const pathNodes = trie.ancestryChain(slugParts)

    if (!pathNodes) {
      return null
    }

    const crumbs: CrumbData[] = pathNodes.map((node, idx) => {
      const crumb = formatCrumb(node.displayName, slug, simplifySlug(node.slug))
      if (idx === 0) {
        crumb.displayName = options.rootName
      }

      if (idx === pathNodes.length - 1) {
        crumb.path = ""
      }

      return crumb
    })

    if (!options.showCurrentPage) {
      crumbs.pop()
    }

    if (crumbs.length > 1 && LANG_SEGMENT_RE.test(pathNodes[1]?.slugSegment ?? "")) {
      crumbs.splice(1, 1)
    }

    return (
      <nav class={classNames(displayClass, "breadcrumb-container")} aria-label="breadcrumbs">
        {crumbs.map((crumb, index) => (
          <div class="breadcrumb-element">
            <a href={crumb.path}>{crumb.displayName}</a>
            {index !== crumbs.length - 1 && <p>{` ${options.spacerSymbol} `}</p>}
          </div>
        ))}
      </nav>
    )
  }
  WikiCommitBreadcrumbs.css = style

  return WikiCommitBreadcrumbs
}) satisfies QuartzComponentConstructor
