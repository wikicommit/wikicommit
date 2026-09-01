// Structural identity of the global graph's control bar (Issue #651).
//
// `renderControls()` used to call `removeAllChildren(bar)` unconditionally, so
// every change a reader made to a control tore the whole bar down and built it
// again: `update()` → `dataset.cfg` → `showGlobalGraph()` → `renderGraph()` →
// `renderControls()`. The graph and the filter results were right, but focus
// and the multi-select's scroll position were lost on every keystroke, so a
// list could not be worked through with the keyboard at all.
//
// The bar can be reused instead, because what decides its *structure* — which
// controls exist and how many options each list holds — is narrower than the
// config that changes as it is used:
//
//   - the facets, collected from the *unfiltered* node set, so narrowing to one
//     language deliberately does not remove the other languages from the list;
//   - the labels, read once from the server-rendered `data-labels` attribute.
//
// Everything else (which options are selected, the toggles, the degree bounds)
// is a *value*, and values are written back into the existing controls rather
// than rebuilt. Reuse therefore has to be paired with that write-back: skipping
// the rebuild without it would leave Reset clearing `dataset.cfg` while the
// controls kept showing the old selection — the display and the actual filter
// disagreeing, which is worse than losing focus.
//
// This module holds only the comparison, so it can be unit-tested in node; the
// DOM side lives in graph.inline.ts.

/** The option lists the bar is built from, as returned by `collectFacets()`. */
export interface ControlFacets {
  langs: string[];
  types: string[];
}

/** A stable string identifying the bar's structure.
 *
 * Label keys are sorted so that two objects carrying the same labels compare
 * equal regardless of the key order they were parsed in — an accidental
 * difference there would force a rebuild (and lose focus) for no reason.
 */
export function controlsSignature(
  facets: ControlFacets,
  labels: Record<string, string | undefined>,
): string {
  const sortedLabels: Record<string, string | undefined> = {};
  for (const key of Object.keys(labels).sort()) {
    sortedLabels[key] = labels[key];
  }
  return JSON.stringify([facets.langs, facets.types, sortedLabels]);
}
