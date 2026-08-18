// node_modules/preact/dist/preact.mjs
var l;
l = { __e: function(n2, l2, u3, t2) {
  for (var i2, r2, o2; l2 = l2.__; ) if ((i2 = l2.__c) && !i2.__) try {
    if ((r2 = i2.constructor) && null != r2.getDerivedStateFromError && (i2.setState(r2.getDerivedStateFromError(n2)), o2 = i2.__d), null != i2.componentDidCatch && (i2.componentDidCatch(n2, t2 || {}), o2 = i2.__d), o2) return i2.__E = i2;
  } catch (l3) {
    n2 = l3;
  }
  throw n2;
} }, "function" == typeof Promise ? Promise.prototype.then.bind(Promise.resolve()) : setTimeout, Math.random().toString(8);

// node_modules/preact/jsx-runtime/dist/jsxRuntime.mjs
var f2 = 0;
function u2(e2, t2, n2, o2, i2, u3) {
  t2 || (t2 = {});
  var a2, c2, p2 = t2;
  if ("ref" in p2) for (c2 in p2 = {}, t2) "ref" == c2 ? a2 = t2[c2] : p2[c2] = t2[c2];
  var l2 = { type: e2, props: p2, key: n2, ref: a2, __k: null, __: null, __b: 0, __e: null, __c: null, constructor: void 0, __v: --f2, __i: -1, __u: 0, __source: i2, __self: u3 };
  return l.vnode && l.vnode(l2), l2;
}

// src/index.tsx
function generateJsonLD(pageData) {
  const frontmatter = pageData.frontmatter;
  if (!frontmatter?.type) return null;
  if (frontmatter.status === "removed") return null;
  const typeStr = String(frontmatter.type).replace(/^schema:/, "");
  if (typeStr.includes("/")) return null;
  const properties = frontmatter.properties && typeof frontmatter.properties === "object" ? frontmatter.properties : {};
  const jsonld = {
    "@context": "https://schema.org",
    "@type": typeStr
  };
  if (frontmatter.title) jsonld.name = frontmatter.title;
  if (frontmatter.tags) jsonld.keywords = frontmatter.tags;
  const sameAs = Array.isArray(frontmatter.sameAs) ? frontmatter.sameAs.filter((x2) => typeof x2 === "string") : [];
  if (frontmatter.wikidata) {
    const qid = String(frontmatter.wikidata).replace(/^wd:/, "");
    sameAs.push(`https://www.wikidata.org/wiki/${qid}`);
  }
  if (sameAs.length > 0) jsonld.sameAs = sameAs;
  const isWikiLink = (v2) => typeof v2 === "string" && v2.startsWith("[[");
  const reservedOutputKeys = /* @__PURE__ */ new Set(["name", "keywords", "sameAs"]);
  for (const [key, value] of Object.entries(properties)) {
    if (reservedOutputKeys.has(key)) continue;
    if (value === void 0 || value === null || value === "") continue;
    if (isWikiLink(value)) continue;
    if (Array.isArray(value)) {
      const filtered = value.filter((v2) => !isWikiLink(v2));
      if (filtered.length === 0) continue;
      jsonld[key] = filtered;
      continue;
    }
    jsonld[key] = value;
  }
  const jsonString = JSON.stringify(jsonld, null, 2).replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026");
  return /* @__PURE__ */ u2(
    "script",
    {
      type: "application/ld+json",
      dangerouslySetInnerHTML: { __html: jsonString }
    }
  );
}
var WikiCommitJsonLD = () => {
  return {
    name: "WikiCommitJsonLD",
    // No-op: Quartz's transformer category validation (config-loader.ts validateCategory)
    // only recognizes textTransform/markdownPlugins/htmlPlugins as evidence of a transformer,
    // so a plugin that only implements externalResources gets skipped as invalid. This
    // satisfies that check without altering the HTML AST; the actual injection happens
    // via externalResources below (see Issue #62).
    htmlPlugins() {
      return [];
    },
    externalResources() {
      return {
        // additionalHead accepts (pageData) => JSX.Element functions;
        // Head.tsx calls each function with per-page fileData at render time.
        additionalHead: [generateJsonLD]
      };
    }
  };
};
var src_default = WikiCommitJsonLD;

export { WikiCommitJsonLD, src_default as default };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map