import { describe, expect, it } from "vitest";
import {
  classifyNode,
  collectFacets,
  computeDegrees,
  filterNodes,
  selectedTypeFacets,
  type GraphLink,
} from "./nodeFilter";

describe("classifyNode", () => {
  it("classifies tag pseudo-nodes", () => {
    expect(classifyNode("tags/engineer")).toEqual({ kind: "tag", isIndex: false });
    expect(classifyNode("tags")).toEqual({ kind: "tag", isIndex: false });
  });

  it("classifies every level of the sources tree as one kind", () => {
    // The landing page, a directory index (Issue #493) and a source page
    // (Issue #476) are all source bookkeeping; a reader wants that tree in the
    // graph or does not.
    for (const id of ["sources", "sources/url/example.com", "sources/url/example.com/article"]) {
      expect(classifyNode(id).kind).toBe("source");
    }
  });

  it("classifies the site root", () => {
    expect(classifyNode("/").kind).toBe("root");
    expect(classifyNode("index").kind).toBe("root");
    expect(classifyNode("").kind).toBe("root");
  });

  it("reads language and type off an entity page", () => {
    expect(classifyNode("ja/person/yamada-taro")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "person",
      isIndex: false,
    });
  });

  it("reads a custom type off its published (flattened) path", () => {
    // Publishing drops a custom type's leading custom/ (Issue #576), so
    // schema:custom/Decision reaches the graph as <lang>/Decision/<slug>.
    expect(classifyNode("ja/decision/adopt-quartz")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "decision",
      isIndex: false,
    });
  });

  it("keeps a doubly-prefixed custom type's surviving custom/ segment", () => {
    // Only the first custom/ is dropped, so custom/custom/Decision still
    // publishes with a custom segment; reading the second segment alone would
    // report it as the single type "custom".
    expect(classifyNode("ja/custom/decision/adopt-quartz")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "custom/decision",
      isIndex: false,
    });
  });

  it("reads index pages through their trailing slash", () => {
    // simplifySlug() only strips a *leading* slash, so a folder page keeps its
    // trailing one: `ja/Person/index` arrives as `ja/person/` (lowercased, like
    // every published slug).
    expect(classifyNode("ja/person/")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "person",
      isIndex: true,
    });
    expect(classifyNode("ja/").isIndex).toBe(true);
    expect(classifyNode("tags/").kind).toBe("tag");
    expect(classifyNode("sources/").kind).toBe("source");
  });

  it("distinguishes index pages from entity pages", () => {
    expect(classifyNode("ja/person").isIndex).toBe(true);
    expect(classifyNode("ja/decision").isIndex).toBe(true);
    expect(classifyNode("ja/person/yamada-taro").isIndex).toBe(false);
    expect(classifyNode("ja/decision/adopt-quartz").isIndex).toBe(false);
    expect(classifyNode("ja/custom/decision").isIndex).toBe(true);
    expect(classifyNode("ja/custom/decision/adopt-quartz").isIndex).toBe(false);
  });

  it("classifies a language root folder page", () => {
    expect(classifyNode("ja")).toEqual({ kind: "entity", lang: "ja", isIndex: true });
  });

  it("checks the reserved prefixes before the entity grammar", () => {
    // Reading `tags/...` as lang=tags would put tag nodes in a language
    // bucket, where a language filter could then take them away.
    expect(classifyNode("tags/engineer").kind).toBe("tag");
    expect(classifyNode("sources/url/x").kind).toBe("source");
  });
});

describe("computeDegrees", () => {
  it("counts only links whose both ends are still present", () => {
    const ids = new Set(["a", "b"]);
    const degrees = computeDegrees(ids, [
      { source: "a", target: "b" },
      { source: "a", target: "gone" },
    ]);
    expect(degrees.get("a")).toBe(1);
    expect(degrees.get("b")).toBe(1);
  });

  it("gives an isolated node a degree of zero rather than leaving it out", () => {
    expect(computeDegrees(new Set(["lonely"]), []).get("lonely")).toBe(0);
  });
});

describe("filterNodes", () => {
  const ids = [
    "ja/person/yamada-taro",
    "ja/decision/adopt-quartz",
    "en/person/yamada-taro",
    "tags/engineer",
    "sources/url/example.com/article",
    "/",
  ];

  it("keeps everything when nothing is selected", () => {
    expect(filterNodes(ids, [], {}).size).toBe(ids.length);
  });

  it("narrows to the selected languages, entity nodes only", () => {
    const kept = filterNodes(ids, [], { langs: ["ja"] });
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
    expect(kept.has("en/person/yamada-taro")).toBe(false);
    // A tag is language-neutral by design and a page shares it with its
    // translations, so a language filter must not take tags away — that is
    // what makes tags the bridge between language clusters in the first place.
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("sources/url/example.com/article")).toBe(true);
    expect(kept.has("/")).toBe(true);
  });

  it("narrows to the selected types", () => {
    const kept = filterNodes(ids, [], { types: ["Decision"] });
    expect(kept.has("ja/decision/adopt-quartz")).toBe(true);
    expect(kept.has("ja/person/yamada-taro")).toBe(false);
  });

  it("also accepts a custom type written the way `type:` writes it", () => {
    // A hand-written quartz.config.yaml names types the way `type:` does, where
    // a custom type keeps its custom/ prefix and is PascalCase; the graph only
    // ever sees the published, flattened, lowercased segment.
    const kept = filterNodes(ids, [], { types: ["custom/Decision"] });
    expect(kept.has("ja/decision/adopt-quartz")).toBe(true);
    expect(kept.has("ja/person/yamada-taro")).toBe(false);
  });

  // Issue #1005. The ids above are published slugs, which Quartz lowercases, so
  // the type read off `ja/person/yamada-taro` is `person`. A config written in
  // the `type:` spelling used to compare case-sensitively against that and keep
  // no entity node at all — while the control bar, whose selection is matched by
  // exact string, drew nothing as selected. The fixtures used to share the
  // config's PascalCase spelling, which is how this stayed green.
  it("matches a PascalCase config against the lowercased slug", () => {
    const kept = filterNodes(ids, [], { types: ["Person"] });
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
    expect(kept.has("en/person/yamada-taro")).toBe(true);
    expect(kept.has("ja/decision/adopt-quartz")).toBe(false);
  });

  // The control bar writes whatever collectFacets() produced. Folding must leave
  // that route exactly as it was.
  it("still matches the spelling the control bar writes", () => {
    const { types } = collectFacets(ids);
    expect(types).toEqual(["decision", "person"]);
    const kept = filterNodes(ids, [], { types: ["decision"] });
    expect(kept.has("ja/decision/adopt-quartz")).toBe(true);
    expect(kept.has("ja/person/yamada-taro")).toBe(false);
  });

  it("keeps a language root through a type filter", () => {
    // It has no type of its own, so a type selection must leave it alone.
    // `showIndexes` is needed to reach the rule at all, because a language root
    // is one of the index nodes now hidden by default (Issue #983) — the rule
    // itself is unchanged.
    expect(
      filterNodes(["ja", "ja/person/x"], [], { types: ["Person"], showIndexes: true }).has("ja"),
    ).toBe(true);
  });

  it("drops the sources tree when showSources is false", () => {
    const kept = filterNodes(ids, [], { showSources: false });
    expect(kept.has("sources/url/example.com/article")).toBe(false);
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
  });

  // The ids below are full entity paths rather than bare names because a
  // single-segment id is a language root, which `classifyNode()` reports as an
  // index and `filterNodes()` now hides by default (Issue #983).
  it("drops nodes below the minimum degree", () => {
    const links = [
      { source: "ja/person/a", target: "ja/person/b" },
      { source: "ja/person/a", target: "ja/person/c" },
    ];
    const kept = filterNodes(
      ["ja/person/a", "ja/person/b", "ja/person/c", "ja/person/lonely"],
      links,
      {
        minDegree: 2,
      },
    );
    expect([...kept]).toEqual(["ja/person/a"]);
  });

  it("drops nodes above the maximum degree, which is what tames a hub tag", () => {
    const links = [
      { source: "ja/person/hub", target: "ja/person/a" },
      { source: "ja/person/hub", target: "ja/person/b" },
      { source: "ja/person/hub", target: "ja/person/c" },
    ];
    const kept = filterNodes(
      ["ja/person/hub", "ja/person/a", "ja/person/b", "ja/person/c"],
      links,
      { maxDegree: 2 },
    );
    expect(kept.has("ja/person/hub")).toBe(false);
    expect(kept.has("ja/person/a")).toBe(true);
  });

  it("computes degree once, against the already-filtered set, without cascading", () => {
    // en/x is removed by the language filter, so ja/b keeps only its one
    // surviving link and falls under minDegree — but ja/a, whose degree drops
    // to 1 only *because* ja/b went away, is not removed in a second pass.
    const links = [
      { source: "ja/person/a", target: "ja/person/b" },
      { source: "ja/person/b", target: "en/person/x" },
      { source: "ja/person/a", target: "ja/person/c" },
    ];
    const kept = filterNodes(["ja/person/a", "ja/person/b", "ja/person/c", "en/person/x"], links, {
      langs: ["ja"],
      minDegree: 2,
    });
    expect([...kept]).toEqual(["ja/person/a"]);
  });

  it("treats 0 as no bound at either end", () => {
    expect(
      filterNodes(["ja/person/a"], [], { minDegree: 0, maxDegree: 0 }).has("ja/person/a"),
    ).toBe(true);
  });
});

// Issue #839: a selection that leaves a tag or source with nothing to link to
// turns it into an unlinked dot, and a field of those reads as "the links broke"
// rather than "nodes were hidden". The prune claims exactly the nodes *this
// filter* disconnected — never one that was already isolated, because that is
// something WikiCommit reports on purpose.
describe("filterNodes prunes what the filter disconnected", () => {
  it("keeps a tag bridging two languages when one language is selected", () => {
    // The case Issue #584 was defending: tags are language-neutral, so they are
    // the only edges between language clusters. The tag still reaches the
    // language that stayed, so it is connected and survives.
    const links = [
      { source: "ja/person/yamada-taro", target: "tags/engineer" },
      { source: "en/person/yamada-taro", target: "tags/engineer" },
    ];
    const kept = filterNodes(
      ["ja/person/yamada-taro", "en/person/yamada-taro", "tags/engineer"],
      links,
      { langs: ["ja"] },
    );
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("en/person/yamada-taro")).toBe(false);
  });

  it("drops a tag with no page of the selected type", () => {
    const links = [
      { source: "ja/person/yamada-taro", target: "tags/engineer" },
      { source: "ja/place/tokyo", target: "tags/city" },
    ];
    const kept = filterNodes(
      ["ja/person/yamada-taro", "ja/place/tokyo", "tags/engineer", "tags/city"],
      links,
      { types: ["Person"] },
    );
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("tags/city")).toBe(false);
  });

  it("keeps a source that was already isolated before any filter", () => {
    // A source that generated no page (`status: failed` / `excluded`) has no
    // links of its own. Hiding it would make the graph the layer that conceals
    // what check_orphans.py and the source pages report (Issue #340 / #547).
    const links = [{ source: "ja/person/yamada-taro", target: "sources/url/a" }];
    const kept = filterNodes(
      ["ja/person/yamada-taro", "sources/url/a", "sources/url/never-used"],
      links,
      { types: ["Person"] },
    );
    expect(kept.has("sources/url/never-used")).toBe(true);
    expect(kept.has("sources/url/a")).toBe(true);
  });

  it("does not cascade when a hub is filtered out", () => {
    // Degrees are taken once, against the set the selection kept. Recomputing
    // after the prune would let one removal pull its neighbours out too, which
    // is the collapse computeDegrees() already refuses to do for minDegree.
    const links = [
      { source: "ja/person/hub", target: "tags/a" },
      { source: "ja/person/hub", target: "sources/url/s" },
      { source: "ja/place/tokyo", target: "tags/a" },
      { source: "ja/place/tokyo", target: "sources/url/s" },
    ];
    const kept = filterNodes(
      ["ja/person/hub", "ja/place/tokyo", "tags/a", "sources/url/s"],
      links,
      { types: ["Place"] },
    );
    // The hub went with the type selection; its neighbours still reach the
    // Place page, so nothing follows it out.
    expect(kept.has("ja/person/hub")).toBe(false);
    expect([...kept].sort()).toEqual(["ja/place/tokyo", "sources/url/s", "tags/a"]);
  });

  it("never prunes an entity node, however isolated the filter leaves it", () => {
    // An orphan page of the selected type is information, not clutter.
    const links = [{ source: "ja/person/yamada-taro", target: "ja/place/tokyo" }];
    const kept = filterNodes(["ja/person/yamada-taro", "ja/place/tokyo"], links, {
      types: ["Person"],
    });
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
  });

  it("applies the degree bounds from the same snapshot as the prune", () => {
    // minDegree reads the pre-prune degrees too, so turning it on cannot make a
    // node disappear that the prune had already accounted for, nor revive one.
    const links = [
      { source: "ja/person/a", target: "tags/t" },
      { source: "ja/place/b", target: "tags/t" },
    ];
    const ids = ["ja/person/a", "ja/place/b", "tags/t"];
    expect([...filterNodes(ids, links, { types: ["Person"], minDegree: 1 })].sort()).toEqual([
      "ja/person/a",
      "tags/t",
    ]);
  });

  it("drops source nodes on a real published shape, where the source tree is self-linked", () => {
    // The shape every published wiki has and the fixtures above did not:
    // convert_wikilinks.py links each source page from content/sources/index.md
    // and again from its directory index, and the root index links `sources`.
    // Those neighbours are all kind === "source", so they survive every
    // selection — a plain degree therefore never reaches 0 and the prune could
    // not fire at all. This is the 100+ node cloud Issue #839 is about.
    const links = [
      { source: "index", target: "sources" },
      { source: "sources", target: "sources/url/a" },
      { source: "sources", target: "sources/url/b" },
      { source: "sources", target: "sources/url/never-used" },
      { source: "sources/url", target: "sources/url/a" },
      { source: "sources/url", target: "sources/url/b" },
      { source: "sources/url", target: "sources/url/never-used" },
      { source: "sources/url/a", target: "ja/person/yamada-taro" },
      { source: "sources/url/b", target: "ja/place/tokyo" },
      { source: "ja/person/yamada-taro", target: "tags/engineer" },
      { source: "ja/place/tokyo", target: "tags/city" },
    ];
    const ids = [
      "index",
      "ja",
      "ja/person/yamada-taro",
      "ja/place/tokyo",
      "tags/engineer",
      "tags/city",
      "sources",
      "sources/url",
      "sources/url/a",
      "sources/url/b",
      "sources/url/never-used",
    ];

    const kept = filterNodes(ids, links, { types: ["Person"] });

    // Reaches the Person page that stayed.
    expect(kept.has("sources/url/a")).toBe(true);
    expect(kept.has("tags/engineer")).toBe(true);
    // Reached only the Place page, which the selection hid.
    expect(kept.has("sources/url/b")).toBe(false);
    expect(kept.has("tags/city")).toBe(false);
    // Generated no page at all (`status: failed` / `excluded`): it reached none
    // before the selection either, so it is isolated for its own reasons and
    // stays visible.
    expect(kept.has("sources/url/never-used")).toBe(true);
  });

  it("does not count a source's sibling index pages as reaching a page", () => {
    // The specific reason the plain degree cannot answer this: the index nodes
    // classify as sources themselves, so they are never filtered away.
    const links = [
      { source: "sources", target: "sources/url/b" },
      { source: "sources/url", target: "sources/url/b" },
      { source: "sources/url/b", target: "ja/place/tokyo" },
    ];
    const kept = filterNodes(
      ["ja/person/a", "ja/place/tokyo", "sources", "sources/url", "sources/url/b"],
      links,
      { types: ["Person"] },
    );
    expect(kept.has("sources/url/b")).toBe(false);
    // The index nodes themselves reached no page even before the selection, so
    // they are not the prune's business either way.
    expect(kept.has("sources")).toBe(true);
  });

  it("accepts a generator for ids", () => {
    // The pre-filter baseline walks the ids a second time; a generator would be
    // empty by then if it were not materialized first.
    function* gen() {
      yield "ja/person/a";
      yield "tags/t";
    }
    const kept = filterNodes(gen(), [{ source: "ja/person/a", target: "tags/t" }], {
      types: ["Person"],
    });
    expect([...kept].sort()).toEqual(["ja/person/a", "tags/t"]);
  });
});

describe("collectFacets", () => {
  it("lists the languages and types actually present, sorted", () => {
    expect(
      collectFacets([
        "ja/person/yamada-taro",
        "en/person/yamada-taro",
        "ja/decision/x",
        "tags/engineer",
        "sources/url/a",
        "/",
        "ja",
      ]),
    ).toEqual({ langs: ["en", "ja"], types: ["decision", "person"] });
  });
});

// ── The overview page (Issue #957) ─────────────────────────────────────────
//
// Issue #585 added `content/overview/` and registered it with neither publishing
// plugin. Issue #946 fixed the explorer half; this is the graph half. Without
// the branch in classifyNode(), `overview/` fell through to the entity grammar
// and read as `{lang: "overview"}` — which put a fake language in the control
// bar and made the page disappear as soon as a reader picked a real one.

describe("the overview page", () => {
  it("classifies as its own kind, not as a language", () => {
    expect(classifyNode("overview/")).toEqual({ kind: "overview", isIndex: false });
    expect(classifyNode("overview")).toEqual({ kind: "overview", isIndex: false });
  });

  it("classifies a split overview page the same way", () => {
    // One page today, but the prefix match is what keeps a future split from
    // breaking this quietly.
    expect(classifyNode("overview/types")).toEqual({ kind: "overview", isIndex: false });
  });

  it("is not isIndex, even though the page is an index.md", () => {
    // `isIndex` is documented as an entity-node concept (a type index or a
    // language root). `tags` and `sources` both answer false; so does this.
    expect(classifyNode("overview/").isIndex).toBe(false);
  });

  it("does not appear in the language facet", () => {
    const facets = collectFacets(["ja/person/a", "overview/", "tags/t", "sources/url/a"]);
    expect(facets.langs).toEqual(["ja"]);
    expect(facets.langs).not.toContain("overview");
  });

  it("is dropped from the graph even with no selection at all", () => {
    const kept = filterNodes(["ja/person/a", "overview/", "tags/t"], [], {});
    expect(kept.has("overview/")).toBe(false);
    expect([...kept].sort()).toEqual(["ja/person/a", "tags/t"]);
  });

  it("is dropped under a language selection too", () => {
    const kept = filterNodes(["ja/person/a", "overview/"], [], { langs: ["ja"] });
    expect(kept.has("overview/")).toBe(false);
    expect(kept.has("ja/person/a")).toBe(true);
  });

  it("does not make an orphan look linked", () => {
    // The whole point. The overview's orphan section links the top 20 orphans,
    // so leaving it in draws them as pages that have a link — the opposite of
    // what that section reports, and of what filterNodes() protects below
    // ("Entity nodes are never pruned … it is an orphan").
    const links = [{ source: "overview/", target: "ja/person/orphan" }];
    const kept = filterNodes(["ja/person/orphan", "overview/"], links, { langs: ["ja"] });
    expect(kept.has("ja/person/orphan")).toBe(true);
    expect(kept.has("overview/")).toBe(false);
    // Degree bounds now see the orphan for what it is: zero visible links.
    const bounded = filterNodes(["ja/person/orphan", "overview/"], links, { minDegree: 1 });
    expect(bounded.has("ja/person/orphan")).toBe(false);
  });

  it("leaves the root index in the graph", () => {
    // Deliberately asymmetric (Issue #957). The root index links `<lang>/`,
    // `sources` and `overview/` — it grows with the language count, never
    // reaches the tens of links a Top-N list does, and states nothing that its
    // own edges contradict.
    const kept = filterNodes(["/", "ja/person/a", "overview/"], [], {});
    expect(kept.has("/")).toBe(true);
    expect(kept.has("overview/")).toBe(false);
  });

  it("does not prune a tag the overview's removal left at zero", () => {
    // Guards the `all`-side construction: the removal must not read as the
    // reader's selection having disconnected something.
    const kept = filterNodes(
      ["tags/t", "overview/"],
      [{ source: "overview/", target: "tags/t" }],
      {},
    );
    expect(kept.has("tags/t")).toBe(true);
  });
});

describe("tag pages reach the node set as real pages", () => {
  // Quartz publishes each tag as a page, so `tags/<name>` is a key of
  // contentIndex.json and enters the global graph's node set through
  // `new Set(data.keys())` — not only through the page -> tag pseudo-links.
  // On `ai-driven-dev-wiki` that is 123 of 969 nodes, every one of them with
  // `links: []` of its own. Gating the pseudo-links alone therefore removed
  // every edge and left the pages behind as unlinked dots (Issue #982).
  //
  // These ids are shaped like that real index: `tags/index` is the landing
  // page, `tags/orphan-tag` is a tag page nothing links to, and
  // `tags/engineer` is one the pseudo-links reach.
  const ids = [
    "ja/person/yamada-taro",
    "ja/place/tokyo",
    "tags",
    "tags/index",
    "tags/engineer",
    "tags/orphan-tag",
    "/",
  ];
  const links = [{ source: "ja/person/yamada-taro", target: "tags/engineer" }];

  it("keeps tag nodes when showTags is absent", () => {
    const kept = filterNodes(ids, links, {});
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("tags/orphan-tag")).toBe(true);
    expect(kept.has("tags")).toBe(true);
  });

  it("drops every tag node when showTags is false, linked or not", () => {
    const kept = filterNodes(ids, links, { showTags: false });
    expect(kept.has("tags/engineer")).toBe(false);
    // The one that made this visible: it has no link to lose, so gating the
    // pseudo-links could never have removed it.
    expect(kept.has("tags/orphan-tag")).toBe(false);
    expect(kept.has("tags/index")).toBe(false);
    expect(kept.has("tags")).toBe(false);
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
    expect(kept.has("/")).toBe(true);
  });

  it("does not prune anything else when tags go away", () => {
    // Turning tags off makes `narrowed` true, which switches the Issue #839
    // prune on for the first time on this path. It must not take the pages
    // with it.
    const kept = filterNodes(ids, links, { showTags: false });
    expect(kept.has("ja/place/tokyo")).toBe(true);
  });

  it("drops the tag named in removeTags, and only that one", () => {
    const kept = filterNodes(ids, links, { removeTags: ["engineer"] });
    expect(kept.has("tags/engineer")).toBe(false);
    expect(kept.has("tags/orphan-tag")).toBe(true);
    // The landing page names no single tag, so removeTags does not select it.
    expect(kept.has("tags")).toBe(true);
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
  });

  it("leaves no isolated dot behind for a removed tag that had links", () => {
    // The pre-fix shape, reproduced as a fixture: the page -> tag pseudo-link
    // was never built for a tag in `removeTags`, so this is the link array
    // filterNodes() used to receive — while `tags/engineer` stayed in the node
    // set, because it is a published page and arrives by the other route. The
    // node has to go away here, or it renders as a point with nothing attached.
    const withoutRemovedTagLink: typeof links = [];
    const kept = filterNodes(ids, withoutRemovedTagLink, { removeTags: ["engineer"] });
    expect(kept.has("tags/engineer")).toBe(false);
    // And the pages themselves are untouched, even though this link array
    // leaves them reaching nothing: an already-isolated node is not the
    // filter's to hide (Issue #839).
    expect(kept.has("ja/person/yamada-taro")).toBe(true);
    expect(kept.has("tags/orphan-tag")).toBe(true);
  });

  it("matches removeTags against the tag page's slugified name", () => {
    // removeTags names the tag as a page's frontmatter writes it; the published
    // slug has been lowercased (Issue #981) and had its whitespace hyphenated
    // by Quartz's slugifier. Both sides are folded before comparing.
    expect(filterNodes(ids, links, { removeTags: ["Engineer"] }).has("tags/engineer")).toBe(false);
    expect(
      filterNodes(["tags/agent-safety"], [], { removeTags: ["Agent Safety"] }).has(
        "tags/agent-safety",
      ),
    ).toBe(false);
    // The fold is case and whitespace only; anything else Quartz rewrites is
    // out of its reach, and the tag is then simply not removed.
    expect(
      filterNodes(["tags/50-percent"], [], { removeTags: ["50%"] }).has("tags/50-percent"),
    ).toBe(true);
  });

  it("takes showTags: false over a removeTags list", () => {
    const kept = filterNodes(ids, links, { showTags: false, removeTags: ["engineer"] });
    expect([...kept].some((id) => id.startsWith("tags"))).toBe(false);
  });
});

describe("build-generated entity index pages", () => {
  // `en/DefinedTerm` stands for a type index, `en` for a language root — both
  // are what `classifyNode()` has always reported as `isIndex`, and both were
  // drawn as ordinary pages because nothing read the flag (Issue #983). The
  // index links to its pages the way `rebuild_index.py` writes it: one
  // `- [[Type/slug]]` per page.
  //
  // Spelled in the file's mixed-case convention. Quartz lowercases a published
  // slug, so the real ids are `en/definedterm` and `en/definedterm/byollm`
  // (Issue #981) — that changes what a type selection has to be spelled as, not
  // which branch `isIndex` takes, and the two ends stay consistent either way.
  const ids = [
    "en/definedterm/byollm",
    "en/definedterm/wikilink",
    "en/definedterm",
    "en",
    "tags/engineer",
    "sources/url/example.com/article",
    "/",
  ];
  const links: GraphLink[] = [
    { source: "en/definedterm", target: "en/definedterm/byollm" },
    { source: "en/definedterm", target: "en/definedterm/wikilink" },
    { source: "en", target: "en/definedterm" },
    { source: "en/definedterm/byollm", target: "tags/engineer" },
    { source: "sources/url/example.com/article", target: "en/definedterm/byollm" },
  ];

  it("drops the type index and the language root by default", () => {
    const kept = filterNodes(ids, links, {});
    expect(kept.has("en/definedterm")).toBe(false);
    expect(kept.has("en")).toBe(false);
  });

  it("keeps the entity pages the index linked to", () => {
    const kept = filterNodes(ids, links, {});
    expect(kept.has("en/definedterm/byollm")).toBe(true);
    expect(kept.has("en/definedterm/wikilink")).toBe(true);
  });

  // `<lang>/<Type>` and `<lang>` are `kind: "entity"`; the root index is
  // `kind: "root"`, and it is kept on purpose — its only outbound links are
  // `<lang>/`, `sources` and `overview/`, so it neither hubs nor lies.
  it("keeps the root index, which is a different kind", () => {
    const kept = filterNodes(ids, links, {});
    expect(kept.has("/")).toBe(true);
  });

  it("keeps them when showIndexes asks for them", () => {
    const kept = filterNodes(ids, links, { showIndexes: true });
    expect(kept.has("en/definedterm")).toBe(true);
    expect(kept.has("en")).toBe(true);
  });

  // The claim the implementation comment makes instead of a test for the
  // overview page, asserted here because this exclusion is configurable and so
  // both branches are reachable from `filterNodes()`'s return value: dropping
  // the indexes must not move Issue #839's prune. A tag or source only loses
  // its node when the filter cut it off from every page it belonged to, and an
  // index is not a page either of them reaches.
  it("does not disconnect the tag or the source", () => {
    const withIndexes = filterNodes(ids, links, { showIndexes: true });
    const withoutIndexes = filterNodes(ids, links, {});
    for (const id of ["tags/engineer", "sources/url/example.com/article"]) {
      expect(withIndexes.has(id)).toBe(true);
      expect(withoutIndexes.has(id)).toBe(true);
    }
  });

  // Dropping at `all`-construction time rather than from `kept` is what keeps
  // `narrowed` meaning "the reader's selection took something away". If the
  // indexes were subtracted from `kept` instead, an unfiltered global graph
  // would look narrowed and lose the early return — and, more visibly, the
  // prune would start running against a baseline that still contained them.
  it("leaves an orphan page visible with no selection, the prune not having run", () => {
    const orphanIds = [...ids, "en/definedterm/lonely"];
    const kept = filterNodes(orphanIds, links, {});
    expect(kept.has("en/definedterm/lonely")).toBe(true);
  });

  // The type index is still an entity node, so a type selection reaches it —
  // it just never survives to be selected while showIndexes is off.
  it("still answers to the type selection when shown", () => {
    const kept = filterNodes(ids, links, { showIndexes: true, types: ["DefinedTerm"] });
    expect(kept.has("en/definedterm")).toBe(true);
    // The language root carries no type, so a type selection leaves it alone
    // (same rule the language-root comment in filterNodes() states).
    expect(kept.has("en")).toBe(true);
  });
});

describe("selectedTypeFacets (Issue #1005)", () => {
  it("maps the type: spelling onto the lowercase facet values", () => {
    expect(
      selectedTypeFacets(["Person", "custom/Decision"], ["decision", "person", "place"]),
    ).toEqual(["decision", "person"]);
  });
  it("returns nothing for an empty selection", () => {
    expect(selectedTypeFacets([], ["person"])).toEqual([]);
  });
});
