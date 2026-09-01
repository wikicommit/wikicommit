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
    /** Type names to show, as they appear in the published path — that is `type:`
     *  minus `schema:`, with a custom type's leading `custom/` dropped as
     *  publishing drops it (Issue #576): `schema:custom/Decision` is `Decision`
     *  here. The `custom/Decision` spelling is accepted too. Empty means every
     *  type. */
    types?: string[];
    /** Show the content/sources/ tree. */
    showSources?: boolean;
}
interface GraphOptions {
    localGraph?: Partial<D3Config>;
    globalGraph?: Partial<D3Config>;
}
declare const _default: (userOpts?: Partial<GraphOptions>) => QuartzComponent;

export { type D3Config, type GraphOptions, _default as WikiCommitGraph };
