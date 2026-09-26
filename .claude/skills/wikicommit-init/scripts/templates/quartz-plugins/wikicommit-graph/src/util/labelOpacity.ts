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
