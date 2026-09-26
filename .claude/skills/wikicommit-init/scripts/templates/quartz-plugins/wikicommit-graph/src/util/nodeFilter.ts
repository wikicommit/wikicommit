// WikiCommit-specific classification of graph nodes, and the filter applied to
// the global graph's node set (Issue #584).
//
// The graph reads `contentIndex.json`, whose entries are
// `{slug, filePath, title, links, tags, content, ...}` — arbitrary frontmatter
// is not carried, so a node's language and type are not available as data and
// have to be recovered from the node id (a Quartz slug). That makes this file
// the one place in the fork that depends on WikiCommit's own path grammar; it
// is kept separate from the inline script so it can be unit-tested.
//
// **A node id is lowercase.** Quartz's slugifier lowercases every segment, so
// `content/ja/Person/yamada-taro.md` becomes the id `ja/person/yamada-taro` and
// the type read off it is `person`, never `Person`. Anything a reader or a
// config writes against these values in PascalCase — the spelling `type:` uses —
// has to be folded before it is compared (`typeMatches()`), exactly as the
// explorer's `sortTier` had to learn for `view` (Issue #981). Tests build their
// ids in the published (lowercase) spelling for the same reason: fixtures that
// shared the config's PascalCase spelling are how both bugs stayed green
// (Issue #1005).

export type NodeKind = "tag" | "source" | "overview" | "root" | "entity";

export interface NodeInfo {
  kind: NodeKind;
  /** Language directory, for entity nodes only (`ja`, `en`, …). */
  lang?: string;
  /** Type segment as it appears in the node id (the **lowercased** Quartz
   *  slug, not the `content/` path), e.g. `person` for `schema:Person`. This is
   *  `type:` minus the `schema:` prefix *and* minus a custom type's leading
   *  `custom/`, which publishing drops (Issue #576), and then lowercased — so
   *  `schema:custom/Decision` reads back as `decision` here. Absent on a
   *  language-root node. */
  type?: string;
  /** True for a `<lang>/<Type>/index.md` type index or a `<lang>` language
   *  root — navigation, not an entity page. */
  isIndex: boolean;
}

/** Classify one graph node id (a simplified Quartz slug, no leading slash).
 *
 * Order matters: `tags/`, `sources/` and `overview` are checked before the entity
 * grammar, because a wiki whose primary language happened to be named `tags`
 * would otherwise be read as a tag tree. All three prefixes are reserved by the
 * publishing layer, so the precedence is not a heuristic. Language directories
 * are two letters, and a Type name only ever appears below a `<lang>/`, so none
 * of the three can collide with a real entity path.
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
  // The build-generated overview page (Issue #585). Registering it here is the
  // half Issue #585 missed: without it `overview/` fell through to the entity
  // grammar and read as `{lang: "overview"}`, which put "overview" in the
  // control bar's language multi-select and made the page vanish the moment a
  // reader picked a real language.
  //
  // `isIndex` is false even though the page is literally an `index.md`.
  // `NodeInfo.isIndex` is defined for entity nodes — a type index or a language
  // root — and `tags` / `sources` both answer false for the same reason. Saying
  // true here would send this node down whichever branch a future `isIndex`
  // check writes on the documented assumption that it is looking at an entity.
  //
  // Prefix-matched like `sources`, not compared for equality: the overview is
  // one page today, and splitting it is out of scope only until it stops
  // fitting on one page. This way that split does not break anything quietly.
  if (id === "overview" || id.startsWith("overview/")) {
    return { kind: "overview", isIndex: false };
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
  /** Type names to keep. Empty/absent means "every type". Compared without
   *  regard to case, so `Person` (the `type:` spelling a hand-written config
   *  uses) and `person` (the slug spelling the control bar writes) both select
   *  the same pages. A custom type may be named either with or without its
   *  `custom/` prefix (`Decision` / `custom/Decision`) — see `typeMatches()`. */
  types?: string[];
  /** Whether `sources/` nodes are shown at all. */
  showSources?: boolean;
  /** Whether `tags/` nodes are shown at all. Absent means shown, matching
   *  `showSources`.
   *
   *  This lives here — and not only where the inline script builds the page →
   *  tag pseudo-links — because a tag node reaches the graph by **two** routes
   *  (Issue #982). Quartz publishes each tag as a real page, so `tags/<name>`
   *  is a key of `contentIndex.json` and enters the global graph's node set
   *  unconditionally; the pseudo-link gate governs only the other route. With
   *  the gate alone, turning tags off removed every edge and left the pages
   *  behind as a field of unlinked dots (123 of 969 nodes on
   *  `ai-driven-dev-wiki`, all of them `links: []`). */
  showTags?: boolean;
  /** Individual tag names to drop, as they are written in a page's `tags:`
   *  frontmatter. Same two-route reason as `showTags`: without this, a tag
   *  named here kept its page node and lost only its links. */
  removeTags?: string[];
  /** Whether build-generated **entity** index pages — a `<lang>/<Type>` type
   *  index or a `<lang>` language root — are shown. Absent means **hidden**,
   *  the opposite polarity from `showSources` / `showTags`, because these are
   *  navigation rather than pages a reader linked to (Issue #983).
   *
   *  This is the first consumer `NodeInfo.isIndex` has ever had. The flag was
   *  computed and documented as "navigation, not an entity page" from the
   *  start, but nothing read it, so a type index entered the graph as an
   *  ordinary page: on `ai-driven-dev-wiki`, `en/definedterm` alone drew 214
   *  links — 44% of that language's pages through one node — which is the hub
   *  Issue #584 set out to remove.
   *
   *  It also makes the graph agree with `check_orphans.py`, which excludes
   *  `index.md` as a *link source* (Issue #678) because a machine-written
   *  `- [[Type/slug]]` is not evidence that anyone referenced the page. Without
   *  this, the graph drew a page that script reports as an orphan as one that
   *  has a link.
   *
   *  The root index (`kind: "root"`) is deliberately **not** covered: its
   *  outbound links are only `<lang>/`, `sources` and `overview/`, so it
   *  neither becomes a hub nor tells a lie. Hence the condition below is
   *  `kind === "entity" && isIndex`.
   *
   *  `sources/`'s own indexes are out of scope and stay reachable through
   *  `showSources`: dropping them would change what Issue #839's prune reads,
   *  and that behaviour was settled against measurements. */
  showIndexes?: boolean;
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

/** True when `type` (a type segment read off a node id, `custom/` already
 *  dropped) is one of the selected names. `types` must already be folded with
 *  `foldTypeName()`; `filterNodes()` does that once on the way in.
 *
 * A hand-written `quartz.config.yaml` names types the way `type:` does — in
 * PascalCase, and with a custom type's `custom/` prefix — while the node id is a
 * lowercased slug with `custom/` dropped. Folding both sides to lowercase and
 * accepting both prefixes keeps that config from silently filtering every page
 * out of the graph (Issue #1005). The control bar always writes the slug
 * spelling, which `collectFacets()` produces and which folding leaves as it is.
 *
 * Folding adds no third spelling to compare: `custom/Decision` folds to
 * `custom/decision`, which is `custom/` + the folded `decision`, so this stays
 * the same two lookups it has always been.
 */
function typeMatches(types: Set<string>, type: string): boolean {
  const folded = foldTypeName(type);
  return types.has(folded) || types.has(`custom/${folded}`);
}

/** The facet values (type segments as `collectFacets()` reports them) that a
 *  configured `types` list selects, in facet order.
 *
 * The control bar marks its options by exact value, but a hand-written config
 * names types in the `type:` spelling (`Person`, `custom/Decision`). Without
 * this mapping such a config filters the graph (`typeMatches()`) while the
 * type select shows nothing chosen — which the bar presents as "unconstrained"
 * (Issue #1005). Uses the same rule as `filterNodes()`, so what the select
 * shows and what the graph keeps cannot disagree.
 */
export function selectedTypeFacets(types: string[], facetTypes: string[]): string[] {
  if (types.length === 0) return [];
  const folded = new Set(types.map(foldTypeName));
  return facetTypes.filter((t) => typeMatches(folded, t));
}

/** Fold a type name to the case its slug segment has.
 *
 * Only case, unlike `foldTagName()`, which also turns whitespace into hyphens.
 * The asymmetry is deliberate: a type name is PascalCase word characters only —
 * no whitespace, no hyphens (the custom type naming rule, which `WIKILINK_RE`'s
 * Type segment enforces by not accepting a hyphen) — so case is the only way a
 * config spelling can differ from its published slug. A tag name is free text,
 * which is why it needs more.
 *
 * `langs` is deliberately **not** folded. ISO 639-1 codes are lowercase by
 * definition and pass through the slugifier unchanged; adding a fold there
 * would change nothing today and would quietly change how a future two-letter
 * type name that collided with a language directory is read.
 */
function foldTypeName(name: string): string {
  return name.toLowerCase();
}

/** The tag name inside a tag node id, or `undefined` for the `tags` landing
 *  page — which names no single tag and so is not what `removeTags` selects. */
function tagNameOf(id: string): string | undefined {
  if (!id.startsWith("tags/")) return undefined;
  const name = id.slice("tags/".length);
  return name.length > 0 ? name : undefined;
}

/** Fold a tag name to the form both sides of the `removeTags` comparison can
 *  be written in.
 *
 * The two sides do not arrive spelled the same way. `removeTags` names the tag
 * as a page's `tags:` frontmatter writes it, which is what the upstream
 * link-building comparison saw; a published tag page's slug has been through
 * Quartz's slugifier, which lowercases (the same lowercasing Issue #981 found
 * in the explorer) and turns whitespace into hyphens. Without folding, a
 * `removeTags` entry that differs from the slug would drop the pseudo-node and
 * leave the page node behind — the very isolated dot Issue #982 is about.
 *
 * **Deliberately partial.** Quartz's slugifier also rewrites `%`, `?`, `#` and
 * more; porting it here would put a second copy of it in a module kept free of
 * Quartz imports so it can be unit-tested, and this repository has paid for
 * that kind of copy before (Issue #677). Case and whitespace are the two the
 * fold covers. A `removeTags` entry differing from the published slug in any
 * other character still matches nothing — the tag simply is not removed, which
 * is visible rather than silent.
 *
 * Over-matching is not a risk: two tags that fold together publish to one page,
 * so this cannot merge nodes that were ever distinct.
 */
function foldTagName(name: string): string {
  return name.toLowerCase().replace(/\s+/g, "-");
}

/** Apply the control bar's filters to a node set.
 *
 * Language and type selections apply to entity nodes only. A tag node has no
 * language by design (`tags` are language-neutral identifiers shared by a page
 * and its translations), and the root and source nodes have none either — so
 * narrowing to one language must not silently take them away. Tags are removed
 * through `showTags` / `removeTags` instead, and sources through `showSources`.
 * All three act here, on the node set, rather than where links are built: a tag
 * page is a real page in `contentIndex.json`, so gating only the pseudo-links
 * left its node behind with no edges (Issue #982).
 *
 * Build-generated entity index pages are dropped unless `showIndexes` asks for
 * them (Issue #983) — the type indexes and language roots `isIndex` has always
 * marked as navigation, and which until then nothing read.
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
  // Folded on the way in, like removeTags below — see typeMatches().
  const types =
    config.types && config.types.length > 0 ? new Set(config.types.map(foldTypeName)) : undefined;
  const showSources = config.showSources !== false;
  const showTags = config.showTags !== false;
  // `=== true`, not `!== false`: this one defaults to hidden (see the field).
  const showIndexes = config.showIndexes === true;
  // Folded on the way in, to be compared against a folded slug segment — see
  // foldTagName().
  const removeTags =
    config.removeTags && config.removeTags.length > 0
      ? new Set(config.removeTags.map(foldTagName))
      : undefined;

  // Materialized up front because it is walked twice: once to apply the
  // selections, and once as the "before" degree baseline below. An Iterable may
  // be a generator, which a second pass would find empty.
  //
  // The overview page is dropped *here*, building `all` without it, rather than
  // removed from `kept` afterwards (Issue #957). Dropping it from `kept` would
  // make `kept.size !== all.size` true on every render, so the default global
  // graph — no selection, no degree bound — would stop taking the early return
  // below and pay for two full `computeEntityDegrees()` walks it has nothing to
  // do with. Built this way, `narrowed` keeps meaning "the reader's selection
  // took something away", which is what the early return and the
  // `pageDegreesBefore` baseline are both written against.
  //
  // The output is the same either way: the overview links only to entity pages,
  // so removing it changes no tag's or source's entity degree and the prune
  // catches nothing new. That is why this is a comment and not a test — the two
  // implementations are indistinguishable from `filterNodes()`'s return value.
  //
  // Why exclude it at all: its "hubs" section links the top 20 most-linked
  // pages, its "wanted" section links every referrer, and its "orphans" section
  // links the top 20 orphans — so on the canvas it is both a hub of the kind
  // Issue #584 set out to remove and a page that **contradicts its own report**,
  // drawing 20 orphans as pages that have a link. `filterNodes()` protects the
  // opposite below ("Entity nodes are never pruned … it is an orphan, which is
  // exactly what the reader should be able to see"), and the overview was
  // quietly undoing it. Readers still reach the page from the root index and
  // from the explorer's top row.
  //
  // Entity index pages (Issue #983) are dropped in the same place and for the
  // same reason, and the "output is the same either way" note above holds for
  // them too: a type index links only to entity pages, and no tag or source
  // links to one, so removing them changes no tag's or source's **entity**
  // degree and the prune below catches nothing new. Entity nodes are never
  // pruned, so the entity pages that lose an index neighbour are unaffected.
  const all = new Set<string>();
  for (const id of ids) {
    const info = classifyNode(id);
    if (info.kind === "overview") continue;
    if (!showIndexes && info.kind === "entity" && info.isIndex) continue;
    all.add(id);
  }

  const kept = new Set<string>();
  for (const id of all) {
    const info = classifyNode(id);
    if (info.kind === "source" && !showSources) continue;
    if (info.kind === "tag") {
      if (!showTags) continue;
      const name = tagNameOf(id);
      if (removeTags && name !== undefined && removeTags.has(foldTagName(name))) continue;
    }
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
