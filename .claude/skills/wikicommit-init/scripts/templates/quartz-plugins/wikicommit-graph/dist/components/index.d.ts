import { QuartzComponent } from '@quartz-community/types';

interface D3Config {
    drag: boolean;
    zoom: boolean;
    depth: number;
    scale: number;
    repelForce: number;
    centerForce: number;
    linkDistance: number;
    fontSize: number;
    opacityScale: number;
    removeTags: string[];
    showTags: boolean;
    focusOnHover?: boolean;
    enableRadial?: boolean;
    /** Show the runtime control bar over the global graph (Issue #584). Ignored
     *  for the local graph, which has neither the room for it nor a node set the
     *  filters can be applied to safely — see the inline script's comment on
     *  `depth >= 0`. */
    showControls?: boolean;
    /** Hide nodes with fewer links than this among the currently shown set.
     *  0 disables the bound. The control bar writes these back at runtime; the
     *  values here are only the starting point. */
    minDegree?: number;
    /** Hide nodes with more links than this among the currently shown set.
     *  0 disables the bound. This is what tames a tag that has become a hub. */
    maxDegree?: number;
    /** Language codes to show. Empty means every language. */
    langs?: string[];
    /** Type names to show, written the way `type:` writes them minus `schema:` —
     *  `Person`, `Decision`, `custom/Decision`. Matched against the node id's
     *  **lowercased** slug segment without regard to case (Issue #1005), and a
     *  custom type matches with or without its leading `custom/`, which
     *  publishing drops (Issue #576). So `Person` and `person` select the same
     *  pages. Empty means every type. */
    types?: string[];
    /** Show the content/sources/ tree. */
    showSources?: boolean;
    /** Show the build-generated entity index pages — a `<lang>/<Type>` type index
     *  or a `<lang>` language root. Defaults to **false**, the opposite of
     *  `showSources` / `showTags`, because these are navigation rather than pages
     *  a reader linked to: on `ai-driven-dev-wiki`, `en/definedterm` alone drew
     *  214 links (Issue #983). The root index is not covered — see
     *  `GraphFilterConfig.showIndexes`.
     *
     *  No control bar item writes this key; it is set here or in
     *  `quartz.config.yaml`. Exposing it in the bar is Issue #985's. */
    showIndexes?: boolean;
}
interface GraphOptions {
    localGraph?: Partial<D3Config>;
    globalGraph?: Partial<D3Config>;
}
declare const _default: (userOpts?: Partial<GraphOptions>) => QuartzComponent;

export { type D3Config, type GraphOptions, _default as WikiCommitGraph };
