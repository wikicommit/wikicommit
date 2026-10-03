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
    /** Steepness of upstream's zoom ramp for label opacity. Applies to the local
     *  graph, and to the global graph only when `labelLimit` is 0 — otherwise
     *  the global graph's labels are chosen by `labelLimit` instead. */
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
    /** Global graph only: how many labels show at once while nothing is hovered.
     *  If the nodes on screen number at most this, all of them are labelled;
     *  otherwise the best-connected this many are (pages first, then tag and
     *  source nodes), at full opacity, and the rest at none. 0 turns the limit
     *  off and the zoom ramp (`opacityScale`) decides, as upstream does. The
     *  control bar can change it at runtime and the change is kept in the
     *  browser until Reset, which returns to this value. */
    labelLimit?: number;
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
     *  `quartz.config.yaml`. It is deliberately not exposed in the bar
     *  (Issue #1018). */
    showIndexes?: boolean;
}
interface GraphOptions {
    localGraph?: Partial<D3Config>;
    globalGraph?: Partial<D3Config>;
}
declare const _default: (userOpts?: Partial<GraphOptions>) => QuartzComponent;

export { type D3Config, type GraphOptions, _default as WikiCommitGraph };
