import type {
  QuartzComponent,
  QuartzComponentConstructor,
  QuartzComponentProps,
} from "@quartz-community/types";
import { classNames } from "../util/lang";
import { i18n } from "../i18n";
import style from "./styles/graph.scss";
// @ts-expect-error - inline script imported as string by esbuild loader
import script from "./scripts/graph.inline.ts";

export interface D3Config {
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

export interface GraphOptions {
  localGraph?: Partial<D3Config>;
  globalGraph?: Partial<D3Config>;
}

const defaultOptions: GraphOptions = {
  localGraph: {
    drag: true,
    zoom: true,
    depth: 1,
    scale: 1.1,
    repelForce: 0.5,
    centerForce: 0.3,
    linkDistance: 30,
    fontSize: 0.6,
    opacityScale: 1,
    showTags: true,
    removeTags: [],
    focusOnHover: false,
    enableRadial: false,
    showControls: false,
  },
  globalGraph: {
    drag: true,
    zoom: true,
    depth: -1,
    scale: 0.9,
    repelForce: 0.5,
    centerForce: 0.2,
    linkDistance: 30,
    fontSize: 0.6,
    opacityScale: 1,
    showTags: true,
    removeTags: [],
    focusOnHover: true,
    enableRadial: true,
    showControls: true,
    minDegree: 0,
    maxDegree: 0,
    langs: [],
    types: [],
    showSources: true,
  },
};

export default ((userOpts?: Partial<GraphOptions>) => {
  const Graph: QuartzComponent = ({ displayClass, cfg }: QuartzComponentProps) => {
    const localGraph = { ...defaultOptions.localGraph, ...userOpts?.localGraph };
    const globalGraph = { ...defaultOptions.globalGraph, ...userOpts?.globalGraph };

    return (
      <div class={classNames(displayClass, "graph")}>
        <h3>{i18n(cfg.locale ?? "en-US").components.graph.title}</h3>
        <div class="graph-outer">
          <div class="graph-container" data-cfg={JSON.stringify(localGraph)}></div>
          <button class="global-graph-icon" aria-label="Global Graph">
            <svg
              version="1.1"
              xmlns="http://www.w3.org/2000/svg"
              xmlnsXlink="http://www.w3.org/1999/xlink"
              x="0px"
              y="0px"
              viewBox="0 0 55 55"
              fill="currentColor"
              xmlSpace="preserve"
            >
              <path
                d="M49,0c-3.309,0-6,2.691-6,6c0,1.035,0.263,2.009,0.726,2.86l-9.829,9.829C32.542,17.634,30.846,17,29,17
                s-3.542,0.634-4.898,1.688l-7.669-7.669C16.785,10.424,17,9.74,17,9c0-2.206-1.794-4-4-4S9,6.794,9,9s1.794,4,4,4
                c0.74,0,1.424-0.215,2.019-0.567l7.669,7.669C21.634,21.458,21,23.154,21,25s0.634,3.542,1.688,4.897L10.024,42.562
                C8.958,41.595,7.549,41,6,41c-3.309,0-6,2.691-6,6s2.691,6,6,6s6-2.691,6-6c0-1.035-0.263-2.009-0.726-2.86l12.829-12.829
                c1.106,0.86,2.44,1.436,3.898,1.619v10.16c-2.833,0.478-5,2.942-5,5.91c0,3.309,2.691,6,6,6s6-2.691,6-6c0-2.967-2.167-5.431-5-5.91
                v-10.16c1.458-0.183,2.792-0.759,3.898-1.619l7.669,7.669C41.215,39.576,41,40.26,41,41c0,2.206,1.794,4,4,4s4-1.794,4-4
                s-1.794-4-4-4c-0.74,0-1.424,0.215-2.019,0.567l-7.669-7.669C36.366,28.542,37,26.846,37,25s-0.634-3.542-1.688-4.897l9.665-9.665
                C46.042,11.405,47.451,12,49,12c3.309,0,6-2.691,6-6S52.309,0,49,0z M11,9c0-1.103,0.897-2,2-2s2,0.897,2,2s-0.897,2-2,2
                S11,10.103,11,9z M6,51c-2.206,0-4-1.794-4-4s1.794-4,4-4s4,1.794,4,4S8.206,51,6,51z M33,49c0,2.206-1.794,4-4,4s-4-1.794-4-4
                s1.794-4,4-4S33,46.794,33,49z M29,31c-3.309,0-6-2.691-6-6s2.691-6,6-6s6,2.691,6,6S32.309,31,29,31z M47,41c0,1.103-0.897,2-2,2
                s-2-0.897-2-2s0.897-2,2-2S47,39.897,47,41z M49,10c-2.206,0-4-1.794-4-4s1.794-4,4-4s4,1.794,4,4S51.206,10,49,10z"
              />
            </svg>
          </button>
        </div>
        <div class="global-graph-outer">
          {/* Left empty on purpose: the bar's contents (the language, type and
              tag option lists) are derived from contentIndex, which only the
              inline script has. It is a sibling of .global-graph-container
              rather than a child because renderGraph() calls
              removeAllChildren() on that container on every render. */}
          <div
            class="global-graph-controls"
            data-labels={JSON.stringify(i18n(cfg.locale ?? "en-US").components.graph.controls)}
          ></div>
          <div class="global-graph-container" data-cfg={JSON.stringify(globalGraph)}></div>
        </div>
      </div>
    );
  };

  Graph.css = style;
  Graph.afterDOMLoaded = script;

  return Graph;
}) satisfies QuartzComponentConstructor;
