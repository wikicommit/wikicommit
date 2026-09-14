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

/** Count, per node id, the links that reach an **entity** node still in `ids`.
 *
 * The prune below asks "does this tag or source still reach a visible page?",
 * and a plain degree cannot answer it: the published source tree is internally
 * linked. `convert_wikilinks.py` links every source page from
 * `content/sources/index.md` (`_write_sources_index()`) and again from its
 * directory index (`_write_source_dir_indexes()`), and the root index links
 * `sources` itself. Those neighbours are all `kind === "source"`, so they
 * survive every language and type selection — leaving every source node at
 * degree ≥ 1 no matter what is selected, which is exactly the 100+ node cloud
 * Issue #839 is about. Counting only entity neighbours is the measurable form of
 * the rule's own one-line justification: a tag and a source exist only through
 * the pages they belong to.
 *
 * Self-links are ignored for the same reason a source's sibling index is: they
 * are not a page this node reaches.
 */
export function computeEntityDegrees(ids: Set<string>, links: GraphLink[]): Map<string, number> {
  const degrees = new Map<string, number>();
  ids.forEach((id) => degrees.set(id, 0));
  for (const link of links) {
    if (!ids.has(link.source) || !ids.has(link.target)) continue;
    if (link.source === link.target) continue;
    if (classifyNode(link.target).kind === "entity") {
      degrees.set(link.source, (degrees.get(link.source) ?? 0) + 1);
    }
    if (classifyNode(link.source).kind === "entity") {
      degrees.set(link.target, (degrees.get(link.target) ?? 0) + 1);
    }
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
 *
 * What *is* taken away is a tag or source node the filter just cut off from every
 * page it belonged to (Issue #839). Links are only
 * drawn when both ends survive, so those render as a field of unlinked dots, and
 * a reader sees "the links broke" rather than "nodes were hidden" — at
 * `ai-driven-dev-wiki`'s scale (100+ source pages) that is most of the canvas.
 * The rule above is not weakened by this: it protects tags that still reach a
 * visible page, which is what Issue #584 was defending. A tag bridging two
 * languages still reaches the language that stayed, so narrowing to one language
 * never costs it.
 */
export function filterNodes(
  ids: Iterable<string>,
  links: GraphLink[],
  config: GraphFilterConfig,
): Set<string> {
  const langs = config.langs && config.langs.length > 0 ? new Set(config.langs) : undefined;
  const types = config.types && config.types.length > 0 ? new Set(config.types) : undefined;
  const showSources = config.showSources !== false;

  // Materialized up front because it is walked twice: once to apply the
  // selections, and once as the "before" degree baseline below. An Iterable may
  // be a generator, which a second pass would find empty.
  const all = new Set(ids);

  const kept = new Set<string>();
  for (const id of all) {
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

  // Nothing was taken away, so nothing can have been *disconnected* either: the
  // two degree maps below would be equal and the prune's predicate (0 now,
  // non-0 before) is unsatisfiable. With no degree bound set either, that leaves
  // the whole walk with nothing to do — the default global graph config
  // (`minDegree: 0` / `maxDegree: 0`, no selection) goes down this path on every
  // re-render, and renderGraph() re-runs on every control-bar change.
  const narrowed = kept.size !== all.size;
  if (!narrowed && minDegree <= 0 && maxDegree <= 0) return kept;

  // One snapshot each, all taken against `kept` — before the prune and before
  // the degree bounds — and every test below is read off them. Recomputing after
  // the prune would cascade for the reason computeDegrees() already states, and
  // is also why the bounds cannot be applied first: they would change the
  // baseline the prune reads.
  //
  // The bounds keep using the plain degree: that is the control bar's
  // "Links per node", and it means every link the reader can see.
  const degrees = computeDegrees(kept, links);
  // The prune uses the entity-only degree instead — see computeEntityDegrees()
  // for why a plain degree cannot answer its question for source nodes.
  const pageDegrees = narrowed ? computeEntityDegrees(kept, links) : undefined;
  // "Did it reach a page before the selection narrowed things?" A node that
  // reaches none in the unfiltered graph reaches none for its own reasons, and
  // those reasons are information WikiCommit reports on purpose — a source that
  // generated no page (`status: failed` / `excluded`), an orphan page
  // (`check_orphans.py`, Issue #340 / #547). The graph must not be the layer
  // that quietly hides them, so the prune only claims nodes this filter
  // disconnected. When the selection kept everything nothing can have been
  // disconnected, so neither map is computed at all.
  const pageDegreesBefore = narrowed ? computeEntityDegrees(all, links) : undefined;

  const result = new Set<string>();
  kept.forEach((id) => {
    const degree = degrees.get(id) ?? 0;
    if (pageDegrees && pageDegreesBefore && (pageDegrees.get(id) ?? 0) === 0) {
      const kind = classifyNode(id).kind;
      // Entity nodes are never pruned: a page of the selected type reaching
      // nothing is not a reason to hide it — it is an orphan, which is exactly
      // what the reader should be able to see.
      if ((kind === "tag" || kind === "source") && (pageDegreesBefore.get(id) ?? 0) > 0) return;
    }
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
