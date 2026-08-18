import { resolveRelative } from '@quartz-community/utils/path';

// src/components/WikiCommitSources.tsx

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    wikicommitSources: {
      title: "Sources",
      inheritedFrom: "Sources inherited from the original page:",
      addedBy: "Added by",
      unknownAuthor: "unknown"
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    wikicommitSources: {
      title: "\u51FA\u5178",
      inheritedFrom: "\u7FFB\u8A33\u5143\u30DA\u30FC\u30B8\u306E\u51FA\u5178\u3092\u8868\u793A\u3057\u3066\u3044\u307E\u3059:",
      addedBy: "\u767B\u9332\u8005:",
      unknownAuthor: "\u4E0D\u660E"
    }
  }
};

// src/i18n/index.ts
var locales = {
  "en-US": en_US_default,
  "ja-JP": ja_JP_default
};
function i18n(locale) {
  return locales[locale] || en_US_default;
}
var LANG_TO_LOCALE = {
  en: "en-US",
  ja: "ja-JP"
};
function resolveLocale(frontmatterLang, cfgLocale) {
  if (typeof frontmatterLang === "string") {
    const mapped = LANG_TO_LOCALE[frontmatterLang];
    if (mapped) return mapped;
  }
  return cfgLocale ?? "en-US";
}

// src/components/styles/wikicommit-sources.scss
var wikicommit_sources_default = ".wikicommit-sources {\n  border-top: 1px solid var(--lightgray);\n  margin-top: 2rem;\n  padding-top: 1rem;\n}\n\n.wikicommit-sources__title {\n  font-size: 1rem;\n  margin: 0 0 0.5rem;\n}\n\n.wikicommit-sources__inherited {\n  font-size: 0.8rem;\n  color: var(--darkgray);\n  margin: 0 0 0.5rem;\n}\n\n.wikicommit-sources__list {\n  margin: 0;\n  padding-left: 1.25rem;\n  font-size: 0.875rem;\n}\n\n.wikicommit-sources__item {\n  margin-bottom: 0.25rem;\n  overflow-wrap: anywhere;\n}\n\n.wikicommit-sources__link {\n  color: var(--secondary);\n}\n\n.wikicommit-sources__text {\n  color: var(--darkgray);\n}";
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
  if ("function" == typeof e2 && (a2 = e2.defaultProps)) for (c2 in a2) void 0 === p2[c2] && (p2[c2] = a2[c2]);
  return l.vnode && l.vnode(l2), l2;
}

// src/components/WikiCommitSources.tsx
function asSourceList(value) {
  return Array.isArray(value) ? value : [];
}
function formatDate(value) {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string" && value) return value;
  return void 0;
}
function translatedFromToRelativePath(translatedFrom) {
  return translatedFrom.trim().replace(/^\.\//, "").replace(/^\.wikicommit\/(entity|wiki)\//, "");
}
function resolveSources(currentSlug, frontmatter, allFiles) {
  const ownSources = asSourceList(frontmatter?.sources);
  if (ownSources.length > 0) return { sources: ownSources, inherited: false };
  const translatedFrom = frontmatter?.translated_from;
  if (typeof translatedFrom !== "string" || translatedFrom.length === 0) {
    return { sources: [], inherited: false };
  }
  const parentRelativePath = translatedFromToRelativePath(translatedFrom);
  const parent = allFiles.find((f3) => f3.relativePath === parentRelativePath);
  if (parent?.frontmatter?.status === "removed") return { sources: [], inherited: false };
  const parentSources = asSourceList(parent?.frontmatter?.sources);
  if (parentSources.length === 0) return { sources: [], inherited: false };
  return {
    sources: parentSources,
    inherited: true,
    parentTitle: parent?.frontmatter?.title ?? parentRelativePath,
    parentHref: parent?.slug ? resolveRelative(currentSlug, parent.slug) : void 0
  };
}
function pathHref(path) {
  const repo = process.env.GITHUB_REPOSITORY;
  if (!repo) return void 0;
  return `https://github.com/${repo}/blob/main/${path.split("/").map(encodeURIComponent).join("/")}`;
}
function renderSource(source, index, t2) {
  switch (source.type) {
    case "path": {
      if (typeof source.path !== "string" || !source.path) return null;
      const href = pathHref(source.path);
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: href ? /* @__PURE__ */ u2("a", { href, class: "wikicommit-sources__link", target: "_blank", rel: "noopener noreferrer", children: source.path }) : /* @__PURE__ */ u2("span", { class: "wikicommit-sources__text", children: source.path }) }, index);
    }
    case "url":
    case "wikicommit": {
      if (typeof source.url !== "string" || !source.url) return null;
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: /* @__PURE__ */ u2("a", { href: source.url, class: "wikicommit-sources__link", target: "_blank", rel: "noopener noreferrer", children: source.url }) }, index);
    }
    case "manual": {
      const author = source.author ?? t2.unknownAuthor;
      const createdAt = formatDate(source.created_at);
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: /* @__PURE__ */ u2("span", { class: "wikicommit-sources__text", children: [
        t2.addedBy,
        " ",
        author,
        createdAt ? ` (${createdAt})` : ""
      ] }) }, index);
    }
    default:
      return null;
  }
}
var WikiCommitSources = ({ fileData, allFiles, cfg }) => {
  const frontmatter = fileData.frontmatter;
  if (frontmatter?.status === "removed") return null;
  const currentSlug = fileData.slug;
  const { sources, inherited, parentTitle, parentHref } = resolveSources(
    currentSlug,
    frontmatter,
    allFiles
  );
  if (sources.length === 0) return null;
  const t2 = i18n(resolveLocale(frontmatter?.lang, cfg?.locale)).components.wikicommitSources;
  const items = sources.map((source, index) => renderSource(source, index, t2)).filter((item) => item !== null);
  if (items.length === 0) return null;
  return /* @__PURE__ */ u2("div", { class: "wikicommit-sources", children: [
    /* @__PURE__ */ u2("h3", { class: "wikicommit-sources__title", children: t2.title }),
    inherited && /* @__PURE__ */ u2("p", { class: "wikicommit-sources__inherited", children: [
      t2.inheritedFrom,
      " ",
      parentHref ? /* @__PURE__ */ u2("a", { href: parentHref, children: parentTitle }) : parentTitle
    ] }),
    /* @__PURE__ */ u2("ul", { class: "wikicommit-sources__list", children: items })
  ] });
};
WikiCommitSources.css = wikicommit_sources_default;
var WikiCommitSources_default = (() => WikiCommitSources);

export { WikiCommitSources_default as WikiCommitSources };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map