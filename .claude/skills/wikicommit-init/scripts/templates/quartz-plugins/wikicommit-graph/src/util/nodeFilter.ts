// WikiCommit-specific classification of graph nodes, and the filter applied to
// the global graph's node set (Issue #584).
//
// The graph reads `contentIndex.json`, whose entries are
// `{slug, filePath, title, links, tags, content, ...}` — arbitrary frontmatter
// is not carried, so a node's language and type are not available as data and
// have to be recovered from the node id (a Quartz slug). That makes this file
// the one place in the fork that depends on WikiCommit's own path grammar; it
// is kept separate from the inline script so it can be unit-tested.

export type NodeKind = "tag" | "source" | "root" | "entity";

export interface NodeInfo {
  kind: NodeKind;
  /** Language directory, for entity nodes only (`ja`, `en`, …). */
  lang?: string;
  /** Type name as it appears in the published path, e.g. `Person`. This is
   *  `type:` minus the `schema:` prefix *and* minus a custom type's leading
   *  `custom/`, which publishing drops (Issue #576) — so `schema:custom/Decision`
   *  reads back as `Decision` here. Absent on a language-root node. */
  type?: string;
  /** True for a `<lang>/<Type>/index.md` type index or a `<lang>` language
   *  root — navigation, not an entity page. */
  isIndex: boolean;
}

/** Classify one graph node id (a simplified Quartz slug, no leading slash).
 *
 * Order matters: `tags/` and `sources/` are checked before the entity grammar,
 * because a wiki whose primary language happened to be named `tags` would
 * otherwise be read as a tag tree. Those two prefixes are reserved by the
 * publishing layer, so the precedence is not a heuristic.
 */
export function classifyNode(id: string): NodeInfo {
  if (id === "" || id === "/" || id === "index") {
    return { kind: "root", isIndex: true };
  }
  if (id === "tags" || id.startsWith("tags/")) {
    return { kind: "tag", isIndex: false };
  }
  // `sources` (the landing page), `sources/url/example.com` (a directory
  // index) and `sources/url/example.com/article` (a source page) are all one
  // kind as far as filtering goes — a reader either wants the source tree in
  // the graph or does not.
  if (id === "sources" || id.startsWith("sources/")) {
    return { kind: "source", isIndex: false };
  }

  const parts = id.split("/").filter((p) => p.length > 0);
  const lang = parts[0];
  if (parts.length === 1) {
    // `ja` — the language root folder page Quartz generates.
    return { kind: "entity", lang, isIndex: true };
  }
  // Publishing drops a custom type's leading `custom/` (Issue #576), so
  // `schema:custom/Decision` normally arrives here as `<lang>/Decision/<slug>`
  // and the second segment is already the whole type name. Only the *first*
  // `custom/` is dropped, so a doubly-prefixed `custom/custom/Decision` still
  // publishes with a `custom` segment; join the second and third segments in
  // that case rather than reporting every such type as the single type
  // `custom`.
  const typeParts = parts[1] === "custom" && parts.length >= 3 ? [parts[1], parts[2]] : [parts[1]];
  const type = typeParts.join("/");
  // `<lang>/<Type>` with nothing after it is the type index page; anything
  // longer is an entity.
  const isIndex = parts.length === typeParts.length + 1;
  return { kind: "entity", lang, type, isIndex };
}

export interface GraphFilterConfig {
  /** Language codes to keep. Empty/absent means "every language". */
  langs?: string[];
  /** Type names to keep. Empty/absent means "every type". A custom type may be
   *  named either as it is published (`Decision`) or as it appears in `type:`
   *  (`custom/Decision`) — see `typeMatches()`. */
  types?: string[];
  /** Whether `sources/` nodes are shown at all. */
  showSources?: boolean;
  /** Drop nodes with fewer than this many links. 0 disables the bound. */
  minDegree?: number;
  /** Drop nodes with more than this many links. 0 disables the bound. */
  maxDegree?: number;
}

export interface GraphLink {
  source: string;
  target: string;
}

/** Count links per node id, over the links whose *both* ends are still in `ids`.
 *
 * Computed once against the already-filtered set rather than iterated to a
 * fixed point: hiding a hub lowers its neighbours' degrees, so repeating the
 * pass cascades and can collapse the graph in ways a reader cannot predict.
 * "How many links this node has among what is currently shown" is the
 * definition that stays explainable.
 */
export function computeDegrees(ids: Set<string>, links: GraphLink[]): Map<string, number> {
  const degrees = new Map<string, number>();
  ids.forEach((id) => degrees.set(id, 0));
  for (const link of links) {
    if (!ids.has(link.source) || !ids.has(link.target)) continue;
    degrees.set(link.source, (degrees.get(link.source) ?? 0) + 1);
    degrees.set(link.target, (degrees.get(link.target) ?? 0) + 1);
  }
  return degrees;
}

/** True when `type` (a published type name, `custom/` already dropped) is one
 *  of the selected names.
 *
 * A hand-written `quartz.config.yaml` names types the way `type:` does, so a
 * custom type is written `custom/Decision` there; the graph only ever sees the
 * published `Decision`. Accepting both spellings keeps that config from
 * silently filtering every custom-type page out of the graph. The control bar
 * always writes the published spelling, which `collectFacets()` produces.
 */
function typeMatches(types: Set<string>, type: string): boolean {
  return types.has(type) || types.has(`custom/${type}`);
}

/** Apply the control bar's filters to a node set.
 *
 * Language and type selections apply to entity nodes only. A tag node has no
 * language by design (`tags` are language-neutral identifiers shared by a page
 * and its translations), and the root and source nodes have none either — so
 * narrowing to one language must not silently take them away. Tags are removed
 * through the existing `showTags` config key instead, and sources through
 * `showSources`.
 */
export function filterNodes(
  ids: Iterable<string>,
  links: GraphLink[],
  config: GraphFilterConfig,
): Set<string> {
  const langs = config.langs && config.langs.length > 0 ? new Set(config.langs) : undefined;
  const types = config.types && config.types.length > 0 ? new Set(config.types) : undefined;
  const showSources = config.showSources !== false;

  const kept = new Set<string>();
  for (const id of ids) {
    const info = classifyNode(id);
    if (info.kind === "source" && !showSources) continue;
    if (info.kind === "entity") {
      if (langs && (info.lang === undefined || !langs.has(info.lang))) continue;
      // A language-root node has no type; it belongs to whichever languages
      // survived the check above rather than to a type selection.
      if (types && info.type !== undefined && !typeMatches(types, info.type)) continue;
    }
    kept.add(id);
  }

  const minDegree = config.minDegree ?? 0;
  const maxDegree = config.maxDegree ?? 0;
  if (minDegree <= 0 && maxDegree <= 0) return kept;

  const degrees = computeDegrees(kept, links);
  const result = new Set<string>();
  kept.forEach((id) => {
    const degree = degrees.get(id) ?? 0;
    if (minDegree > 0 && degree < minDegree) return;
    if (maxDegree > 0 && degree > maxDegree) return;
    result.add(id);
  });
  return result;
}

/** Language codes and type names present in a node set, each sorted, for
 *  building the control bar's option lists. */
export function collectFacets(ids: Iterable<string>): { langs: string[]; types: string[] } {
  const langs = new Set<string>();
  const types = new Set<string>();
  for (const id of ids) {
    const info = classifyNode(id);
    if (info.kind !== "entity") continue;
    if (info.lang) langs.add(info.lang);
    if (info.type) types.add(info.type);
  }
  return { langs: [...langs].sort(), types: [...types].sort() };
}
