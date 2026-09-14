import { describe, expect, it } from "vitest";
import { classifyNode, collectFacets, computeDegrees, filterNodes } from "./nodeFilter";

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
    expect(classifyNode("ja/Person/yamada-taro")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "Person",
      isIndex: false,
    });
  });

  it("reads a custom type off its published (flattened) path", () => {
    // Publishing drops a custom type's leading custom/ (Issue #576), so
    // schema:custom/Decision reaches the graph as <lang>/Decision/<slug>.
    expect(classifyNode("ja/Decision/adopt-quartz")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "Decision",
      isIndex: false,
    });
  });

  it("keeps a doubly-prefixed custom type's surviving custom/ segment", () => {
    // Only the first custom/ is dropped, so custom/custom/Decision still
    // publishes with a custom segment; reading the second segment alone would
    // report it as the single type "custom".
    expect(classifyNode("ja/custom/Decision/adopt-quartz")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "custom/Decision",
      isIndex: false,
    });
  });

  it("reads index pages through their trailing slash", () => {
    // simplifySlug() only strips a *leading* slash, so a folder page keeps its
    // trailing one: `ja/Person/index` arrives as `ja/Person/`.
    expect(classifyNode("ja/Person/")).toEqual({
      kind: "entity",
      lang: "ja",
      type: "Person",
      isIndex: true,
    });
    expect(classifyNode("ja/").isIndex).toBe(true);
    expect(classifyNode("tags/").kind).toBe("tag");
    expect(classifyNode("sources/").kind).toBe("source");
  });

  it("distinguishes index pages from entity pages", () => {
    expect(classifyNode("ja/Person").isIndex).toBe(true);
    expect(classifyNode("ja/Decision").isIndex).toBe(true);
    expect(classifyNode("ja/Person/yamada-taro").isIndex).toBe(false);
    expect(classifyNode("ja/Decision/adopt-quartz").isIndex).toBe(false);
    expect(classifyNode("ja/custom/Decision").isIndex).toBe(true);
    expect(classifyNode("ja/custom/Decision/adopt-quartz").isIndex).toBe(false);
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
    "ja/Person/yamada-taro",
    "ja/Decision/adopt-quartz",
    "en/Person/yamada-taro",
    "tags/engineer",
    "sources/url/example.com/article",
    "/",
  ];

  it("keeps everything when nothing is selected", () => {
    expect(filterNodes(ids, [], {}).size).toBe(ids.length);
  });

  it("narrows to the selected languages, entity nodes only", () => {
    const kept = filterNodes(ids, [], { langs: ["ja"] });
    expect(kept.has("ja/Person/yamada-taro")).toBe(true);
    expect(kept.has("en/Person/yamada-taro")).toBe(false);
    // A tag is language-neutral by design and a page shares it with its
    // translations, so a language filter must not take tags away — that is
    // what makes tags the bridge between language clusters in the first place.
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("sources/url/example.com/article")).toBe(true);
    expect(kept.has("/")).toBe(true);
  });

  it("narrows to the selected types", () => {
    const kept = filterNodes(ids, [], { types: ["Decision"] });
    expect(kept.has("ja/Decision/adopt-quartz")).toBe(true);
    expect(kept.has("ja/Person/yamada-taro")).toBe(false);
  });

  it("also accepts a custom type written the way `type:` writes it", () => {
    // quartz.config.yaml is written by hand against `type:` values, where a
    // custom type keeps its custom/ prefix; the graph only ever sees the
    // published, flattened name.
    const kept = filterNodes(ids, [], { types: ["custom/Decision"] });
    expect(kept.has("ja/Decision/adopt-quartz")).toBe(true);
    expect(kept.has("ja/Person/yamada-taro")).toBe(false);
  });

  it("keeps a language root through a type filter", () => {
    // It has no type of its own; dropping it would strand the folder page.
    expect(filterNodes(["ja", "ja/Person/x"], [], { types: ["Person"] }).has("ja")).toBe(true);
  });

  it("drops the sources tree when showSources is false", () => {
    const kept = filterNodes(ids, [], { showSources: false });
    expect(kept.has("sources/url/example.com/article")).toBe(false);
    expect(kept.has("ja/Person/yamada-taro")).toBe(true);
  });

  it("drops nodes below the minimum degree", () => {
    const links = [
      { source: "a", target: "b" },
      { source: "a", target: "c" },
    ];
    const kept = filterNodes(["a", "b", "c", "lonely"], links, { minDegree: 2 });
    expect([...kept]).toEqual(["a"]);
  });

  it("drops nodes above the maximum degree, which is what tames a hub tag", () => {
    const links = [
      { source: "hub", target: "a" },
      { source: "hub", target: "b" },
      { source: "hub", target: "c" },
    ];
    const kept = filterNodes(["hub", "a", "b", "c"], links, { maxDegree: 2 });
    expect(kept.has("hub")).toBe(false);
    expect(kept.has("a")).toBe(true);
  });

  it("computes degree once, against the already-filtered set, without cascading", () => {
    // en/x is removed by the language filter, so ja/b keeps only its one
    // surviving link and falls under minDegree — but ja/a, whose degree drops
    // to 1 only *because* ja/b went away, is not removed in a second pass.
    const links = [
      { source: "ja/Person/a", target: "ja/Person/b" },
      { source: "ja/Person/b", target: "en/Person/x" },
      { source: "ja/Person/a", target: "ja/Person/c" },
    ];
    const kept = filterNodes(["ja/Person/a", "ja/Person/b", "ja/Person/c", "en/Person/x"], links, {
      langs: ["ja"],
      minDegree: 2,
    });
    expect([...kept]).toEqual(["ja/Person/a"]);
  });

  it("treats 0 as no bound at either end", () => {
    expect(filterNodes(["a"], [], { minDegree: 0, maxDegree: 0 }).has("a")).toBe(true);
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
      { source: "ja/Person/yamada-taro", target: "tags/engineer" },
      { source: "en/Person/yamada-taro", target: "tags/engineer" },
    ];
    const kept = filterNodes(
      ["ja/Person/yamada-taro", "en/Person/yamada-taro", "tags/engineer"],
      links,
      { langs: ["ja"] },
    );
    expect(kept.has("tags/engineer")).toBe(true);
    expect(kept.has("en/Person/yamada-taro")).toBe(false);
  });

  it("drops a tag with no page of the selected type", () => {
    const links = [
      { source: "ja/Person/yamada-taro", target: "tags/engineer" },
      { source: "ja/Place/tokyo", target: "tags/city" },
    ];
    const kept = filterNodes(
      ["ja/Person/yamada-taro", "ja/Place/tokyo", "tags/engineer", "tags/city"],
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
    const links = [{ source: "ja/Person/yamada-taro", target: "sources/url/a" }];
    const kept = filterNodes(
      ["ja/Person/yamada-taro", "sources/url/a", "sources/url/never-used"],
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
      { source: "ja/Person/hub", target: "tags/a" },
      { source: "ja/Person/hub", target: "sources/url/s" },
      { source: "ja/Place/tokyo", target: "tags/a" },
      { source: "ja/Place/tokyo", target: "sources/url/s" },
    ];
    const kept = filterNodes(
      ["ja/Person/hub", "ja/Place/tokyo", "tags/a", "sources/url/s"],
      links,
      { types: ["Place"] },
    );
    // The hub went with the type selection; its neighbours still reach the
    // Place page, so nothing follows it out.
    expect(kept.has("ja/Person/hub")).toBe(false);
    expect([...kept].sort()).toEqual(["ja/Place/tokyo", "sources/url/s", "tags/a"]);
  });

  it("never prunes an entity node, however isolated the filter leaves it", () => {
    // An orphan page of the selected type is information, not clutter.
    const links = [{ source: "ja/Person/yamada-taro", target: "ja/Place/tokyo" }];
    const kept = filterNodes(["ja/Person/yamada-taro", "ja/Place/tokyo"], links, {
      types: ["Person"],
    });
    expect(kept.has("ja/Person/yamada-taro")).toBe(true);
  });

  it("applies the degree bounds from the same snapshot as the prune", () => {
    // minDegree reads the pre-prune degrees too, so turning it on cannot make a
    // node disappear that the prune had already accounted for, nor revive one.
    const links = [
      { source: "ja/Person/a", target: "tags/t" },
      { source: "ja/Place/b", target: "tags/t" },
    ];
    const ids = ["ja/Person/a", "ja/Place/b", "tags/t"];
    expect([...filterNodes(ids, links, { types: ["Person"], minDegree: 1 })].sort()).toEqual([
      "ja/Person/a",
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
      { source: "sources/url/a", target: "ja/Person/yamada-taro" },
      { source: "sources/url/b", target: "ja/Place/tokyo" },
      { source: "ja/Person/yamada-taro", target: "tags/engineer" },
      { source: "ja/Place/tokyo", target: "tags/city" },
    ];
    const ids = [
      "index",
      "ja",
      "ja/Person/yamada-taro",
      "ja/Place/tokyo",
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
      { source: "sources/url/b", target: "ja/Place/tokyo" },
    ];
    const kept = filterNodes(
      ["ja/Person/a", "ja/Place/tokyo", "sources", "sources/url", "sources/url/b"],
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
      yield "ja/Person/a";
      yield "tags/t";
    }
    const kept = filterNodes(gen(), [{ source: "ja/Person/a", target: "tags/t" }], {
      types: ["Person"],
    });
    expect([...kept].sort()).toEqual(["ja/Person/a", "tags/t"]);
  });
});

describe("collectFacets", () => {
  it("lists the languages and types actually present, sorted", () => {
    expect(
      collectFacets([
        "ja/Person/yamada-taro",
        "en/Person/yamada-taro",
        "ja/Decision/x",
        "tags/engineer",
        "sources/url/a",
        "/",
        "ja",
      ]),
    ).toEqual({ langs: ["en", "ja"], types: ["Decision", "Person"] });
  });
});
