import { resolveRelative } from '@quartz-community/utils/path';

// src/components/WikiCommitLanguageSwitcher.tsx

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    wikicommitLanguageSwitcher: {
      label: "Read in:"
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    wikicommitLanguageSwitcher: {
      label: "\u3053\u306E\u8A00\u8A9E\u3067\u8AAD\u3080:"
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

// src/components/styles/wikicommit-language-switcher.scss
var wikicommit_language_switcher_default = ".wikicommit-language-switcher {\n  display: flex;\n  flex-wrap: wrap;\n  align-items: baseline;\n  gap: 0.35rem;\n  font-size: 0.75rem;\n  margin-bottom: 0.75rem;\n}\n\n.wikicommit-language-switcher__label {\n  color: var(--darkgray);\n}\n\n.wikicommit-language-switcher__list {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 0.5rem;\n  margin: 0;\n  padding: 0;\n  list-style: none;\n}\n\n.wikicommit-language-switcher__item {\n  display: inline-flex;\n}\n\n.wikicommit-language-switcher__link {\n  color: var(--secondary);\n}\n\n.wikicommit-language-switcher__current {\n  color: var(--dark);\n  font-weight: 600;\n}";
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

// src/components/WikiCommitLanguageSwitcher.tsx
var LANGUAGE_NAMES = {
  ja: "\u65E5\u672C\u8A9E",
  en: "English",
  zh: "\u4E2D\u6587",
  ko: "\uD55C\uAD6D\uC5B4",
  fr: "Fran\xE7ais",
  de: "Deutsch",
  es: "Espa\xF1ol",
  pt: "Portugu\xEAs",
  ru: "\u0420\u0443\u0441\u0441\u043A\u0438\u0439",
  it: "Italiano",
  vi: "Ti\u1EBFng Vi\u1EC7t",
  th: "\u0E44\u0E17\u0E22",
  id: "Bahasa Indonesia",
  ar: "\u0627\u0644\u0639\u0631\u0628\u064A\u0629"
};
function languageName(lang) {
  return LANGUAGE_NAMES[lang] ?? lang.toUpperCase();
}
var LANG_SEGMENT_RE = /^[a-z]{2}$/;
function typeSlugKey(relativePath) {
  const slashIndex = relativePath.indexOf("/");
  if (slashIndex === -1) return null;
  const lang = relativePath.slice(0, slashIndex);
  if (!LANG_SEGMENT_RE.test(lang)) return null;
  const key = relativePath.slice(slashIndex + 1);
  if (!key) return null;
  return { lang, key };
}
function buildLanguageIndex(allFiles) {
  const index = /* @__PURE__ */ new Map();
  for (const file of allFiles) {
    if (file.frontmatter?.status === "removed") continue;
    const relativePath = file.relativePath;
    if (!relativePath) continue;
    const parsed = typeSlugKey(relativePath);
    if (!parsed) continue;
    const slug = file.slug;
    if (!slug) continue;
    let byLang = index.get(parsed.key);
    if (!byLang) {
      byLang = /* @__PURE__ */ new Map();
      index.set(parsed.key, byLang);
    }
    byLang.set(parsed.lang, slug);
  }
  return index;
}
var WikiCommitLanguageSwitcher = ({
  fileData,
  allFiles,
  cfg,
  ctx
}) => {
  const frontmatter = fileData.frontmatter;
  if (frontmatter?.status === "removed") return null;
  const currentRelativePath = fileData.relativePath;
  if (!currentRelativePath) return null;
  const current = typeSlugKey(currentRelativePath);
  if (!current) return null;
  const currentSlug = fileData.slug;
  if (!currentSlug) return null;
  const typedCtx = ctx ?? {};
  typedCtx.wikicommitLanguageIndex ??= buildLanguageIndex(allFiles);
  const siblings = typedCtx.wikicommitLanguageIndex.get(current.key) ?? /* @__PURE__ */ new Map();
  if (siblings.size <= 1) return null;
  const t2 = i18n(cfg?.locale ?? "en-US").components.wikicommitLanguageSwitcher;
  const entries = [...siblings.entries()].sort(([a2], [b2]) => a2.localeCompare(b2)).map(([lang, slug]) => ({
    lang,
    href: lang === current.lang ? "" : resolveRelative(currentSlug, slug),
    isCurrent: lang === current.lang
  }));
  return /* @__PURE__ */ u2("div", { class: "wikicommit-language-switcher", children: [
    /* @__PURE__ */ u2("span", { class: "wikicommit-language-switcher__label", children: t2.label }),
    /* @__PURE__ */ u2("ul", { class: "wikicommit-language-switcher__list", children: entries.map((entry) => /* @__PURE__ */ u2("li", { class: "wikicommit-language-switcher__item", children: entry.isCurrent ? /* @__PURE__ */ u2("span", { class: "wikicommit-language-switcher__current", "aria-current": "true", children: languageName(entry.lang) }) : /* @__PURE__ */ u2("a", { href: entry.href, class: "wikicommit-language-switcher__link", children: languageName(entry.lang) }) }, entry.lang)) })
  ] });
};
WikiCommitLanguageSwitcher.css = wikicommit_language_switcher_default;
var WikiCommitLanguageSwitcher_default = (() => WikiCommitLanguageSwitcher);

export { WikiCommitLanguageSwitcher_default as WikiCommitLanguageSwitcher };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map