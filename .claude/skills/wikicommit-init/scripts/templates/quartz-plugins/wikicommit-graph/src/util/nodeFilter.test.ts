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
