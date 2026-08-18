import { createRequire } from 'node:module';
import { classNames } from '@quartz-community/utils/lang';
import { resolveRelative as resolveRelative$1, splitAnchor, slugifyFilePath } from '@quartz-community/utils/path';

createRequire(import.meta.url);
function resolveRelative(current, target) {
  return resolveRelative$1(current, target);
}
function slugifyWikilinkTarget(target) {
  const [rawPath, anchor] = splitAnchor(target);
  if (!rawPath) return anchor;
  const pathWithExt = rawPath.endsWith(".md") ? rawPath : `${rawPath}.md`;
  const slug = slugifyFilePath(pathWithExt);
  return slug + anchor;
}

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    wikicommitProperties: {
      title: "Properties"
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    wikicommitProperties: {
      title: "\u30D7\u30ED\u30D1\u30C6\u30A3"
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

// src/components/styles/wikicommit-properties.scss
var wikicommit_properties_default = '.wikicommit-properties {\n  margin: 0.5rem 0 1rem;\n  border: 1px solid var(--lightgray);\n  border-radius: 5px;\n  font-size: 0.9rem;\n}\n.wikicommit-properties[open] > .wikicommit-properties-header {\n  border-bottom: 1px solid var(--lightgray);\n}\n.wikicommit-properties .wikicommit-properties-header {\n  display: flex;\n  align-items: center;\n  gap: 0.5rem;\n  padding: 0.4rem 0.8rem;\n  cursor: pointer;\n  user-select: none;\n  list-style: none;\n  color: var(--darkgray);\n  font-weight: 600;\n}\n.wikicommit-properties .wikicommit-properties-header::-webkit-details-marker {\n  display: none;\n}\n.wikicommit-properties .wikicommit-properties-header::before {\n  content: "";\n  display: inline-block;\n  width: 0.5em;\n  height: 0.5em;\n  border-right: 2px solid var(--darkgray);\n  border-bottom: 2px solid var(--darkgray);\n  transform: rotate(-45deg);\n  transition: transform 0.2s ease;\n}\n.wikicommit-properties[open] > .wikicommit-properties-header::before {\n  transform: rotate(45deg);\n}\n.wikicommit-properties .wikicommit-properties-count {\n  margin-left: auto;\n  font-size: 0.75rem;\n  color: var(--gray);\n  font-weight: 400;\n}\n.wikicommit-properties .wikicommit-properties-table {\n  width: 100%;\n  border-collapse: collapse;\n  table-layout: fixed;\n}\n.wikicommit-properties .wikicommit-properties-row {\n  border-bottom: 1px solid var(--lightgray);\n}\n.wikicommit-properties .wikicommit-properties-row:last-child {\n  border-bottom: none;\n}\n.wikicommit-properties .wikicommit-properties-key {\n  width: 35%;\n  padding: 0.35rem 0.8rem;\n  color: var(--gray);\n  font-size: 0.85rem;\n  vertical-align: top;\n  word-break: break-word;\n}\n.wikicommit-properties .wikicommit-properties-value {\n  padding: 0.35rem 0.8rem;\n  vertical-align: top;\n  word-break: break-word;\n}\n.wikicommit-properties .wikicommit-properties-empty {\n  color: var(--gray);\n  font-style: italic;\n}\n.wikicommit-properties .wikicommit-properties-boolean input[type=checkbox] {\n  pointer-events: none;\n  margin: 0;\n  vertical-align: middle;\n}\n.wikicommit-properties .wikicommit-properties-number {\n  font-family: var(--codeFont);\n  font-size: 0.85em;\n}\n.wikicommit-properties .wikicommit-properties-link {\n  text-decoration: none;\n  color: var(--secondary);\n}\n.wikicommit-properties .wikicommit-properties-link:hover {\n  text-decoration: underline;\n}\n.wikicommit-properties .wikicommit-properties-separator {\n  color: var(--gray);\n}\n.wikicommit-properties .wikicommit-properties-list {\n  display: inline;\n}\n.wikicommit-properties .wikicommit-properties-tags {\n  display: inline-flex;\n}\n.wikicommit-properties .wikicommit-properties-tags .tag-link {\n  display: inline-block;\n  padding: 0.1rem 0.4rem;\n  border-radius: 3px;\n  background: var(--highlight);\n  color: var(--secondary);\n  font-size: 0.85em;\n  text-decoration: none;\n}\n.wikicommit-properties .wikicommit-properties-tags .tag-link:hover {\n  background: var(--secondary);\n  color: var(--light);\n}\n.wikicommit-properties .wikicommit-properties-object code {\n  font-size: 0.85em;\n  padding: 0.1rem 0.3rem;\n  border-radius: 3px;\n  background: var(--highlight);\n  word-break: break-all;\n}';

// src/components/scripts/wikicommitProperties.inline.ts
var wikicommitProperties_inline_default = 'var o=Object.hasOwnProperty;function e(u){return u.document.body.dataset.slug}var C="wikicommit-properties-collapsed:";function A(){return C+e(window)}function n(){let u=document.querySelector("details.wikicommit-properties");if(!u)return;let D=A(),F=localStorage.getItem(D);if(F!==null){let E=F==="true";u.open=!E}let t=()=>{localStorage.setItem(D,String(!u.open))};u.addEventListener("toggle",t),typeof window<"u"&&window.addCleanup&&window.addCleanup(()=>{u.removeEventListener("toggle",t)})}document.addEventListener("nav",()=>{n()});document.addEventListener("render",()=>{n()});\n';
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

// src/components/WikiCommitProperties.tsx
var WIKILINK_RE = /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g;
var MDLINK_RE = /\[([^\]]*)\]\(([^)]+)\)/g;
var URL_RE = /https?:\/\/[^\s<>]+/g;
var TRAILING_PUNCTUATION_RE = /[.,;:!?。、！？…‘’“”]+$/;
function trimUnbalancedTrailingParen(url) {
  while (url.endsWith(")")) {
    const opens = (url.match(/\(/g) ?? []).length;
    const closes = (url.match(/\)/g) ?? []).length;
    if (closes <= opens) break;
    url = url.slice(0, -1);
  }
  return url;
}
function lookupHref(ctx, slugifiedTarget) {
  return ctx.resolvedLinks[slugifiedTarget] ?? resolveRelative(ctx.slug, slugifiedTarget);
}
function renderTextWithLinks(text, ctx) {
  const segments = [];
  for (const match of text.matchAll(WIKILINK_RE)) {
    const target = match[1];
    const display = match[2] ?? target;
    const href = lookupHref(ctx, slugifyWikilinkTarget(target));
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: /* @__PURE__ */ u2("a", { href, class: "internal internal-link wikicommit-properties-link", children: display })
    });
  }
  for (const match of text.matchAll(MDLINK_RE)) {
    const overlaps = segments.some(
      (s2) => match.index < s2.end && match.index + match[0].length > s2.start
    );
    if (overlaps) continue;
    const display = match[1];
    const href = match[2];
    const isExternal = href.startsWith("http://") || href.startsWith("https://");
    const resolvedHref = isExternal ? href : lookupHref(ctx, href);
    segments.push({
      start: match.index,
      end: match.index + match[0].length,
      node: /* @__PURE__ */ u2(
        "a",
        {
          href: resolvedHref,
          class: classNames(
            isExternal ? "external external-link" : "internal internal-link",
            "wikicommit-properties-link"
          ),
          ...isExternal ? { target: "_blank", rel: "noopener noreferrer" } : {},
          children: display || href
        }
      )
    });
  }
  for (const match of text.matchAll(URL_RE)) {
    const overlaps = segments.some(
      (s2) => match.index < s2.end && match.index + match[0].length > s2.start
    );
    if (overlaps) continue;
    const url = trimUnbalancedTrailingParen(match[0].replace(TRAILING_PUNCTUATION_RE, ""));
    if (url.replace(/^https?:\/\//, "").length === 0) continue;
    segments.push({
      start: match.index,
      end: match.index + url.length,
      node: /* @__PURE__ */ u2(
        "a",
        {
          href: url,
          class: "external external-link wikicommit-properties-link",
          target: "_blank",
          rel: "noopener noreferrer",
          children: url
        }
      )
    });
  }
  if (segments.length === 0) return [text];
  segments.sort((a2, b2) => a2.start - b2.start);
  const result = [];
  let cursor = 0;
  for (const seg of segments) {
    if (seg.start > cursor) {
      result.push(text.slice(cursor, seg.start));
    }
    result.push(seg.node);
    cursor = seg.end;
  }
  if (cursor < text.length) {
    result.push(text.slice(cursor));
  }
  return result;
}
function renderValue(value, ctx) {
  if (value === null || value === void 0) {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-empty", children: "\u2014" });
  }
  if (typeof value === "boolean") {
    return /* @__PURE__ */ u2("span", { class: classNames("wikicommit-properties-boolean", value ? "is-true" : "is-false"), children: /* @__PURE__ */ u2("input", { type: "checkbox", checked: value, disabled: true }) });
  }
  if (typeof value === "number") {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-number", children: value });
  }
  if (typeof value === "string") {
    const parts = renderTextWithLinks(value, ctx);
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-text", children: parts });
  }
  if (Array.isArray(value)) {
    const items = value.map((item, idx) => {
      const rendered = renderValue(item, ctx);
      return /* @__PURE__ */ u2(S, { children: [
        idx > 0 && /* @__PURE__ */ u2("span", { class: "wikicommit-properties-separator", children: ", " }),
        rendered
      ] });
    });
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-list", children: items });
  }
  if (typeof value === "object") {
    return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-object", children: /* @__PURE__ */ u2("code", { children: JSON.stringify(value) }) });
  }
  return String(value);
}
function renderTagList(tags, ctx) {
  const items = tags.map((tag, idx) => {
    const href = resolveRelative(ctx.slug, `tags/${tag}`);
    return /* @__PURE__ */ u2(S, { children: [
      idx > 0 && /* @__PURE__ */ u2("span", { class: "wikicommit-properties-separator", children: ", " }),
      /* @__PURE__ */ u2("a", { href, class: "internal internal-link tag-link", children: tag })
    ] });
  });
  return /* @__PURE__ */ u2("span", { class: "wikicommit-properties-tags", children: items });
}
var WikiCommitProperties_default = ((opts) => {
  const { collapsed = false } = opts ?? {};
  const Component = (props) => {
    const wcProps = props.fileData?.wikicommitProperties;
    if (!wcProps) return null;
    if (wcProps.showProperties === false) return null;
    if (wcProps.showProperties !== true && wcProps.hideView) return null;
    const properties = wcProps.properties;
    const entries = Object.entries(properties);
    if (entries.length === 0) return null;
    const frontmatter = props.fileData?.frontmatter;
    const t2 = i18n(resolveLocale(frontmatter?.lang, props.cfg?.locale)).components.wikicommitProperties;
    const ctx = {
      slug: props.fileData?.slug ?? "",
      resolvedLinks: wcProps.resolvedLinks ?? {}
    };
    const isCollapsed = wcProps.collapseProperties ?? collapsed;
    return /* @__PURE__ */ u2(
      "details",
      {
        class: classNames(props.displayClass, "wikicommit-properties", "metadata-container"),
        open: !isCollapsed,
        "data-collapsed": isCollapsed,
        children: [
          /* @__PURE__ */ u2("summary", { class: "wikicommit-properties-header", children: [
            /* @__PURE__ */ u2("span", { class: "wikicommit-properties-title", children: t2.title }),
            /* @__PURE__ */ u2("span", { class: "wikicommit-properties-count", children: entries.length })
          ] }),
          /* @__PURE__ */ u2("table", { class: "wikicommit-properties-table", children: /* @__PURE__ */ u2("tbody", { children: entries.map(([key, value]) => /* @__PURE__ */ u2("tr", { class: "wikicommit-properties-row metadata-property", children: [
            /* @__PURE__ */ u2("td", { class: "wikicommit-properties-key metadata-property-key", children: key }),
            /* @__PURE__ */ u2("td", { class: "wikicommit-properties-value metadata-property-value", children: key === "tags" && Array.isArray(value) ? renderTagList(value, ctx) : renderValue(value, ctx) })
          ] }, key)) }) })
        ]
      }
    );
  };
  Component.css = wikicommit_properties_default;
  Component.afterDOMLoaded = wikicommitProperties_inline_default;
  return Component;
});

export { WikiCommitProperties_default as WikiCommitPropertiesComponent };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map