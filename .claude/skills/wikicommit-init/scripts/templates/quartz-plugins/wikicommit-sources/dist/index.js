import { resolveRelative } from '@quartz-community/utils/path';

// src/components/WikiCommitSources.tsx

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    wikicommitSources: {
      title: "Sources",
      inheritedFrom: "Sources inherited from the original page:",
      derivedFrom: "This page was synthesized from the following pages in this wiki:",
      unavailablePage: "removed or not published",
      addedBy: "Added by",
      unknownAuthor: "unknown",
      adaptationNotice: "This page was summarized and restructured from the sources above by an LLM; it is not a verbatim reproduction. Any license shown applies to the source it is listed with, not to this page as a whole.",
      licenseScopeNotice: "Any license shown applies to the source it is listed with, not to this page as a whole."
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    wikicommitSources: {
      title: "\u51FA\u5178",
      inheritedFrom: "\u7FFB\u8A33\u5143\u30DA\u30FC\u30B8\u306E\u51FA\u5178\u3092\u8868\u793A\u3057\u3066\u3044\u307E\u3059:",
      derivedFrom: "\u3053\u306E\u30DA\u30FC\u30B8\u306F Wiki \u5185\u306E\u4EE5\u4E0B\u306E\u30DA\u30FC\u30B8\u3092\u5408\u6210\u3057\u305F\u3082\u306E\u3067\u3059:",
      unavailablePage: "\u524A\u9664\u6E08\u307F\uFF0F\u672A\u516C\u958B",
      addedBy: "\u767B\u9332\u8005:",
      unknownAuthor: "\u4E0D\u660E",
      adaptationNotice: "\u3053\u306E\u30DA\u30FC\u30B8\u306F\u4E0A\u8A18\u306E\u51FA\u5178\u3092 LLM \u304C\u8981\u7D04\u30FB\u518D\u69CB\u6210\u3057\u305F\u3082\u306E\u3067\u3042\u308A\u3001\u9010\u8A9E\u8EE2\u8F09\u3067\u306F\u3042\u308A\u307E\u305B\u3093\u3002\u8868\u793A\u3055\u308C\u3066\u3044\u308B\u30E9\u30A4\u30BB\u30F3\u30B9\u306F\u4F75\u8A18\u3055\u308C\u305F\u51FA\u5178\u306B\u5BFE\u3059\u308B\u3082\u306E\u3067\u3042\u308A\u3001\u3053\u306E\u30DA\u30FC\u30B8\u5168\u4F53\u306B\u5BFE\u3059\u308B\u3082\u306E\u3067\u306F\u3042\u308A\u307E\u305B\u3093\u3002",
      licenseScopeNotice: "\u8868\u793A\u3055\u308C\u3066\u3044\u308B\u30E9\u30A4\u30BB\u30F3\u30B9\u306F\u4F75\u8A18\u3055\u308C\u305F\u51FA\u5178\u306B\u5BFE\u3059\u308B\u3082\u306E\u3067\u3042\u308A\u3001\u3053\u306E\u30DA\u30FC\u30B8\u5168\u4F53\u306B\u5BFE\u3059\u308B\u3082\u306E\u3067\u306F\u3042\u308A\u307E\u305B\u3093\u3002"
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
var wikicommit_sources_default = ".wikicommit-sources {\n  border-top: 1px solid var(--lightgray);\n  margin-top: 2rem;\n  padding-top: 1rem;\n}\n\n.wikicommit-sources__title {\n  font-size: 1rem;\n  margin: 0 0 0.5rem;\n}\n\n.wikicommit-sources__inherited {\n  font-size: 0.8rem;\n  color: var(--darkgray);\n  margin: 0 0 0.5rem;\n}\n\n.wikicommit-sources__list {\n  margin: 0;\n  padding-left: 1.25rem;\n  font-size: 0.875rem;\n}\n\n.wikicommit-sources__item {\n  margin-bottom: 0.25rem;\n  overflow-wrap: anywhere;\n}\n\n.wikicommit-sources__link {\n  color: var(--secondary);\n}\n\n.wikicommit-sources__text {\n  color: var(--darkgray);\n}\n\n.wikicommit-sources__license {\n  color: var(--darkgray);\n}\n\n.wikicommit-sources__license-link {\n  color: var(--darkgray);\n}\n\n.wikicommit-sources__notice {\n  font-size: 0.8rem;\n  color: var(--darkgray);\n  margin: 0.5rem 0 0;\n}\n\n.wikicommit-sources__derived {\n  font-size: 0.8rem;\n  color: var(--darkgray);\n  margin: 0.5rem 0;\n}\n\n.wikicommit-sources__unavailable {\n  color: var(--darkgray);\n}";
var l;
function S(n2) {
  return n2.children;
}
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
function asDerivedList(value) {
  return Array.isArray(value) ? value : [];
}
var CC_LICENSE_RE = /^CC-(BY(?:-NC)?(?:-SA|-ND)?)-(\d(?:\.\d)?)$/i;
function licenseHref(license) {
  if (/^CC0-1\.0$/i.test(license)) {
    return "https://creativecommons.org/publicdomain/zero/1.0/";
  }
  const m2 = CC_LICENSE_RE.exec(license);
  const variant = m2?.[1];
  const version = m2?.[2];
  if (!variant || !version) return void 0;
  return `https://creativecommons.org/licenses/${variant.toLowerCase()}/${version}/`;
}
function renderLicense(license) {
  if (typeof license !== "string" || !license.trim()) return null;
  const value = license.trim();
  const href = licenseHref(value);
  return /* @__PURE__ */ u2("span", { class: "wikicommit-sources__license", children: [
    " (",
    href ? (
      // Deliberately not rel="license": per the HTML spec that keyword says the
      // linked document is the license *of the current page*, which is exactly
      // the claim the adaptation notice below disclaims (a page can merge several
      // differently-licensed sources). Issue #558.
      /* @__PURE__ */ u2("a", { href, class: "wikicommit-sources__license-link", target: "_blank", rel: "noopener noreferrer", children: value })
    ) : value,
    ")"
  ] });
}
function formatDate(value) {
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === "string" && value) return value;
  return void 0;
}
function entityPathToRelativePath(entityPath) {
  return entityPath.trim().replace(/^\.\//, "").replace(/^\.wikicommit\/(entity|wiki)\//, "").replace(/^([^/]+)\/custom\//, "$1/");
}
function resolveDerivations(currentSlug, entries, allFiles) {
  const resolved = [];
  for (const entry of entries) {
    const path = entry?.path;
    if (typeof path !== "string" || path.trim() === "") continue;
    const relativePath = entityPathToRelativePath(path);
    const page = allFiles.find((f3) => f3.relativePath === relativePath);
    if (!page || page.frontmatter?.status === "removed") {
      resolved.push({ label: relativePath, unavailable: true });
      continue;
    }
    resolved.push({
      label: page.frontmatter?.title ?? relativePath,
      href: page.slug ? resolveRelative(currentSlug, page.slug) : void 0,
      unavailable: false
    });
  }
  return resolved;
}
function emptyProvenance() {
  return { sources: [], derivations: [], inherited: false };
}
function resolveProvenance(currentSlug, frontmatter, allFiles) {
  const ownSources = asSourceList(frontmatter?.sources);
  const ownDerivations = resolveDerivations(
    currentSlug,
    asDerivedList(frontmatter?.derived_from),
    allFiles
  );
  if (ownSources.length > 0 || ownDerivations.length > 0) {
    return { sources: ownSources, derivations: ownDerivations, inherited: false };
  }
  const translatedFrom = frontmatter?.translated_from;
  if (typeof translatedFrom !== "string" || translatedFrom.length === 0) {
    return emptyProvenance();
  }
  const parentRelativePath = entityPathToRelativePath(translatedFrom);
  const parent = allFiles.find((f3) => f3.relativePath === parentRelativePath);
  if (parent?.frontmatter?.status === "removed") return emptyProvenance();
  const parentSources = asSourceList(parent?.frontmatter?.sources);
  const parentDerivations = resolveDerivations(
    currentSlug,
    asDerivedList(parent?.frontmatter?.derived_from),
    allFiles
  );
  if (parentSources.length === 0 && parentDerivations.length === 0) return emptyProvenance();
  return {
    sources: parentSources,
    derivations: parentDerivations,
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
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: [
        href ? /* @__PURE__ */ u2("a", { href, class: "wikicommit-sources__link", target: "_blank", rel: "noopener noreferrer", children: source.path }) : /* @__PURE__ */ u2("span", { class: "wikicommit-sources__text", children: source.path }),
        renderLicense(source.license)
      ] }, index);
    }
    case "url":
    case "wikicommit": {
      if (typeof source.url !== "string" || !source.url) return null;
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: [
        /* @__PURE__ */ u2("a", { href: source.url, class: "wikicommit-sources__link", target: "_blank", rel: "noopener noreferrer", children: source.url }),
        renderLicense(source.license)
      ] }, index);
    }
    case "manual": {
      const author = source.author ?? t2.unknownAuthor;
      const createdAt = formatDate(source.created_at);
      return /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: [
        /* @__PURE__ */ u2("span", { class: "wikicommit-sources__text", children: [
          t2.addedBy,
          " ",
          author,
          createdAt ? ` (${createdAt})` : ""
        ] }),
        renderLicense(source.license)
      ] }, index);
    }
    default:
      return null;
  }
}
var WikiCommitSources = ({ fileData, allFiles, cfg }) => {
  const frontmatter = fileData.frontmatter;
  if (frontmatter?.status === "removed") return null;
  const currentSlug = fileData.slug;
  const { sources, derivations, inherited, parentTitle, parentHref } = resolveProvenance(
    currentSlug,
    frontmatter,
    allFiles
  );
  if (sources.length === 0 && derivations.length === 0) return null;
  const t2 = i18n(resolveLocale(frontmatter?.lang, cfg?.locale)).components.wikicommitSources;
  const items = sources.map((source, index) => renderSource(source, index, t2)).filter((item) => item !== null);
  if (items.length === 0 && derivations.length === 0) return null;
  const adapted = sources.some((source) => source.type !== "manual");
  const showsALicense = sources.some(
    (source) => typeof source.license === "string" && source.license.trim() !== ""
  );
  const notice = adapted ? t2.adaptationNotice : showsALicense ? t2.licenseScopeNotice : void 0;
  return /* @__PURE__ */ u2("div", { class: "wikicommit-sources", children: [
    /* @__PURE__ */ u2("h3", { class: "wikicommit-sources__title", children: t2.title }),
    inherited && /* @__PURE__ */ u2("p", { class: "wikicommit-sources__inherited", children: [
      t2.inheritedFrom,
      " ",
      parentHref ? /* @__PURE__ */ u2("a", { href: parentHref, children: parentTitle }) : parentTitle
    ] }),
    items.length > 0 && /* @__PURE__ */ u2("ul", { class: "wikicommit-sources__list", children: items }),
    derivations.length > 0 && /* @__PURE__ */ u2(S, { children: [
      /* @__PURE__ */ u2("p", { class: "wikicommit-sources__derived", children: t2.derivedFrom }),
      /* @__PURE__ */ u2("ul", { class: "wikicommit-sources__list", children: derivations.map((derivation, index) => /* @__PURE__ */ u2("li", { class: "wikicommit-sources__item", children: [
        derivation.href ? /* @__PURE__ */ u2("a", { href: derivation.href, class: "wikicommit-sources__link", children: derivation.label }) : /* @__PURE__ */ u2("span", { class: "wikicommit-sources__text", children: derivation.label }),
        derivation.unavailable && /* @__PURE__ */ u2("span", { class: "wikicommit-sources__unavailable", children: [
          " (",
          t2.unavailablePage,
          ")"
        ] })
      ] }, index)) })
    ] }),
    notice && /* @__PURE__ */ u2("p", { class: "wikicommit-sources__notice", children: notice })
  ] });
};
WikiCommitSources.css = wikicommit_sources_default;
var WikiCommitSources_default = (() => WikiCommitSources);

export { WikiCommitSources_default as WikiCommitSources };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map