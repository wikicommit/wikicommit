// How opaque a node's label is drawn (Issue #986).
//
// Split out of `graph.inline.ts` for the reason `nodeFilter.ts` and
// `controlBar.ts` were: the inline script is assembled by an esbuild loader at
// build time and carries `@ts-nocheck`, so nothing in it can be unit-tested and
// nothing in it is type-checked. The decision here is small but it is the whole
// of what Issue #986 changed, and the graph cannot be looked at in this
// repository (Issue #81) — a truth table that can be asserted directly is the
// only verification available.
//
// Three separate places in the inline script used to write `label.alpha`, and
// between them the neighbourhood of a hovered node was never distinguished from
// the rest of the graph: labels were created at 0, the zoom handler assigned one
// scale-derived value to every label that was not active (skipping the active
// ones rather than raising them, so they kept whatever the previous zoom had
// left), and the hover path raised only the hovered node's own label.
// `renderNodes()` and `renderLinks()` had been splitting 1 / 0.2 on the same
// `active` flag the whole time.

/** The opacity the zoom level alone gives every label.
 *
 * `zoomK` is the d3 transform's scale factor and `opacityScale` the config key
 * of the same name. The curve is upstream's and is deliberately unchanged: what
 * Issue #986 fixed is that hovering could not override it, not the shape of the
 * ramp. At the default `opacityScale: 1` this is 0 until the reader zooms past
 * 1×, which is why an untouched global graph shows no labels at all.
 */
export function zoomLabelAlpha(zoomK: number, opacityScale: number): number {
  return Math.max((zoomK * opacityScale - 1) / 3.75, 0);
}

/** Hover first, zoom second.
 *
 * `hovered` is "this node is the one under the pointer", `active` is "this node
 * is in the hovered node's neighbourhood" (the flag `updateHoverInfo()` sets and
 * `renderNodes()` already reads), and `focusing` is "something is hovered *and*
 * `focusOnHover` is on".
 *
 * Non-neighbours go to 0 rather than to the 0.2 that nodes and links use while
 * focusing: a dot at 0.2 still gives the graph its shape, but text at 0.2 is
 * unreadable overlap, and reading names is the whole reason to hover.
 *
 * The hovered node's own label was never gated on `focusOnHover` upstream and
 * still is not — hence the first branch is checked before `focusing`.
 */
export function labelAlpha(
  hovered: boolean,
  active: boolean,
  focusing: boolean,
  zoomAlpha: number,
): number {
  if (hovered) return 1;
  if (focusing) return active ? 1 : 0;
  return zoomAlpha;
}

// ---------------------------------------------------------------------------
// The label limit (global graph only)
//
// `zoomLabelAlpha()` looks at the magnification and nothing else, so the same
// zoom that suits a 50-page wiki fills the screen with text on a 1000-page one,
// and every zoom between "none" and "all" lays every label down half
// transparent — which conveys neither the graph's shape nor any name. The
// global graph therefore decides its resting labels by how many fit on screen:
// everything in the viewport while that is at most `limit`, otherwise the
// `limit` best-connected nodes in it. A chosen label is drawn at 1 and the rest
// at 0; there is no half-transparent middle any more.
//
// The local graph keeps the zoom ramp — it holds a neighbourhood, not the
// whole wiki, and has no control bar to change the limit from.

/** The limit the global graph uses when nothing configures one. */
export const DEFAULT_LABEL_LIMIT = 40;

/** A node as far as label selection is concerned. `x` / `y` are simulation
 *  coordinates (the frame `viewport` is given in), `degree` is its link count
 *  in the drawn graph, and `secondary` marks a tag or source node. */
export interface LabelCandidate {
  id: string;
  x: number | null | undefined;
  y: number | null | undefined;
  degree: number;
  secondary: boolean;
}

/** The visible rectangle, in simulation coordinates. */
export interface Viewport {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

/** Read a limit out of config or the control bar. Anything that is not a
 *  non-negative finite number falls back to the default, and fractions are
 *  floored — a limit counts labels. */
export function normalizeLabelLimit(value: unknown): number {
  const n = typeof value === "string" ? parseInt(value, 10) : value;
  if (typeof n !== "number" || !Number.isFinite(n) || n < 0) return DEFAULT_LABEL_LIMIT;
  return Math.floor(n);
}

function byRank(a: LabelCandidate, b: LabelCandidate): number {
  // Ties broken by id so the chosen set does not flicker between frames that
  // happen to visit equal-degree nodes in a different order.
  if (b.degree !== a.degree) return b.degree - a.degree;
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
}

/** The ids whose labels rest at full opacity, or `null` for "no limit — use the
 *  zoom ramp" (`limit` 0).
 *
 * Pages are ranked first by degree; tag and source nodes only fill slots the
 * pages left over. Both can be turned off from the bar, and a tag that has
 * become a hub would otherwise take a top slot from the pages the reader came
 * to read.
 */
export function selectLabels(
  candidates: readonly LabelCandidate[],
  viewport: Viewport,
  limit: number,
): Set<string> | null {
  if (!(limit > 0)) return null;
  const pages: LabelCandidate[] = [];
  const others: LabelCandidate[] = [];
  for (const c of candidates) {
    if (c.x == null || c.y == null) continue;
    if (c.x < viewport.x0 || c.x > viewport.x1 || c.y < viewport.y0 || c.y > viewport.y1) {
      continue;
    }
    (c.secondary ? others : pages).push(c);
  }
  if (pages.length + others.length <= limit) {
    return new Set([...pages, ...others].map((c) => c.id));
  }
  pages.sort(byRank);
  const chosen = new Set<string>();
  for (const c of pages) {
    if (chosen.size >= limit) return chosen;
    chosen.add(c.id);
  }
  others.sort(byRank);
  for (const c of others) {
    if (chosen.size >= limit) break;
    chosen.add(c.id);
  }
  return chosen;
}

/** The opacity a label rests at when nothing overrides it — the value
 *  `labelAlpha()` receives as `zoomAlpha`.
 *
 * `selected` is `undefined` when no limit is in force (the local graph, or a
 * limit of 0), in which case the zoom ramp decides as it always did. */
export function restingLabelAlpha(selected: boolean | undefined, zoomAlpha: number): number {
  if (selected === undefined) return zoomAlpha;
  return selected ? 1 : 0;
}
