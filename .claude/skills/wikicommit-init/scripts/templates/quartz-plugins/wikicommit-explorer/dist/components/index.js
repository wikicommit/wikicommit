import { classNames } from '@quartz-community/utils/lang';

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
  if ("function" == typeof e2 && (a2 = e2.defaultProps)) for (c2 in a2) void 0 === p2[c2] && (p2[c2] = a2[c2]);
  return l.vnode && l.vnode(l2), l2;
}

// src/components/OverflowList.tsx
var OverflowList = ({
  children,
  ...props
}) => {
  return /* @__PURE__ */ u2("ul", { ...props, class: [props.class, "overflow"].filter(Boolean).join(" "), id: props.id, children: [
    children,
    /* @__PURE__ */ u2("li", { class: "overflow-end" })
  ] });
};
var numLists = 0;
var OverflowList_default = () => {
  const id = `list-${numLists++}`;
  return {
    OverflowList: (props) => /* @__PURE__ */ u2(OverflowList, { ...props, id }),
    overflowListAfterDOMLoaded: `
document.addEventListener("nav", (e) => {
  const ul = document.getElementById("${id}")
  if (!ul) return

  const end = ul.querySelector(".overflow-end")
  if (!end) return

  const scrollContainer = ul.parentElement
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const parentUl = entry.target.parentElement
      if (!parentUl) return
      if (entry.isIntersecting) {
        parentUl.classList.remove("gradient-active")
      } else {
        parentUl.classList.add("gradient-active")
      }
    }
  }, scrollContainer ? { root: scrollContainer } : undefined)

  observer.observe(end)
  window.addCleanup(() => observer.disconnect())
})
`
  };
};

// src/i18n/locales/en-US.ts
var en_US_default = {
  components: {
    explorer: {
      title: "Explorer"
    }
  }
};

// src/i18n/locales/en-GB.ts
var en_GB_default = {
  components: {
    explorer: {
      title: "Explorer"
    }
  }
};

// src/i18n/locales/ar-SA.ts
var ar_SA_default = {
  components: {
    explorer: {
      title: "\u0627\u0644\u0645\u0633\u062A\u0639\u0631\u0636"
    }
  }
};

// src/i18n/locales/ca-ES.ts
var ca_ES_default = {
  components: {
    explorer: {
      title: "Explorador"
    }
  }
};

// src/i18n/locales/cs-CZ.ts
var cs_CZ_default = {
  components: {
    explorer: {
      title: "Proch\xE1zet"
    }
  }
};

// src/i18n/locales/de-DE.ts
var de_DE_default = {
  components: {
    explorer: {
      title: "Explorer"
    }
  }
};

// src/i18n/locales/es-ES.ts
var es_ES_default = {
  components: {
    explorer: {
      title: "Explorador"
    }
  }
};

// src/i18n/locales/fa-IR.ts
var fa_IR_default = {
  components: {
    explorer: {
      title: "\u0645\u0637\u0627\u0644\u0628"
    }
  }
};

// src/i18n/locales/fi-FI.ts
var fi_FI_default = {
  components: {
    explorer: {
      title: "Selain"
    }
  }
};

// src/i18n/locales/fr-FR.ts
var fr_FR_default = {
  components: {
    explorer: {
      title: "Explorateur"
    }
  }
};

// src/i18n/locales/he-IL.ts
var he_IL_default = {
  components: {
    explorer: {
      title: "\u05E1\u05D9\u05D9\u05E8"
    }
  }
};

// src/i18n/locales/hu-HU.ts
var hu_HU_default = {
  components: {
    explorer: {
      title: "F\xE1jlb\xF6ng\xE9sz\u0151"
    }
  }
};

// src/i18n/locales/id-ID.ts
var id_ID_default = {
  components: {
    explorer: {
      title: "Penjelajah"
    }
  }
};

// src/i18n/locales/it-IT.ts
var it_IT_default = {
  components: {
    explorer: {
      title: "Esplora"
    }
  }
};

// src/i18n/locales/ja-JP.ts
var ja_JP_default = {
  components: {
    explorer: {
      title: "\u30A8\u30AF\u30B9\u30D7\u30ED\u30FC\u30E9\u30FC"
    }
  }
};

// src/i18n/locales/kk-KZ.ts
var kk_KZ_default = {
  components: {
    explorer: {
      title: "\u0417\u0435\u0440\u0442\u0442\u0435\u0443\u0448\u0456"
    }
  }
};

// src/i18n/locales/ko-KR.ts
var ko_KR_default = {
  components: {
    explorer: {
      title: "\uD0D0\uC0C9\uAE30"
    }
  }
};

// src/i18n/locales/lt-LT.ts
var lt_LT_default = {
  components: {
    explorer: {
      title: "Nar\u0161ykl\u0117"
    }
  }
};

// src/i18n/locales/nb-NO.ts
var nb_NO_default = {
  components: {
    explorer: {
      title: "Utforsker"
    }
  }
};

// src/i18n/locales/nl-NL.ts
var nl_NL_default = {
  components: {
    explorer: {
      title: "Verkenner"
    }
  }
};

// src/i18n/locales/pl-PL.ts
var pl_PL_default = {
  components: {
    explorer: {
      title: "Przegl\u0105daj"
    }
  }
};

// src/i18n/locales/pt-BR.ts
var pt_BR_default = {
  components: {
    explorer: {
      title: "Explorador"
    }
  }
};

// src/i18n/locales/ro-RO.ts
var ro_RO_default = {
  components: {
    explorer: {
      title: "Explorator"
    }
  }
};

// src/i18n/locales/ru-RU.ts
var ru_RU_default = {
  components: {
    explorer: {
      title: "\u041F\u0440\u043E\u0432\u043E\u0434\u043D\u0438\u043A"
    }
  }
};

// src/i18n/locales/th-TH.ts
var th_TH_default = {
  components: {
    explorer: {
      title: "\u0E23\u0E32\u0E22\u0E01\u0E32\u0E23\u0E2B\u0E19\u0E49\u0E32"
    }
  }
};

// src/i18n/locales/tr-TR.ts
var tr_TR_default = {
  components: {
    explorer: {
      title: "Gezgin"
    }
  }
};

// src/i18n/locales/uk-UA.ts
var uk_UA_default = {
  components: {
    explorer: {
      title: "\u041F\u0440\u043E\u0432\u0456\u0434\u043D\u0438\u043A"
    }
  }
};

// src/i18n/locales/vi-VN.ts
var vi_VN_default = {
  components: {
    explorer: {
      title: "N\u1ED9i dung"
    }
  }
};

// src/i18n/locales/zh-CN.ts
var zh_CN_default = {
  components: {
    explorer: {
      title: "\u63A2\u7D22"
    }
  }
};

// src/i18n/locales/zh-TW.ts
var zh_TW_default = {
  components: {
    explorer: {
      title: "\u63A2\u7D22"
    }
  }
};

// src/i18n/index.ts
var locales = {
  "en-US": en_US_default,
  "en-GB": en_GB_default,
  "ar-SA": ar_SA_default,
  "ca-ES": ca_ES_default,
  "cs-CZ": cs_CZ_default,
  "de-DE": de_DE_default,
  "es-ES": es_ES_default,
  "fa-IR": fa_IR_default,
  "fi-FI": fi_FI_default,
  "fr-FR": fr_FR_default,
  "he-IL": he_IL_default,
  "hu-HU": hu_HU_default,
  "id-ID": id_ID_default,
  "it-IT": it_IT_default,
  "ja-JP": ja_JP_default,
  "kk-KZ": kk_KZ_default,
  "ko-KR": ko_KR_default,
  "lt-LT": lt_LT_default,
  "nb-NO": nb_NO_default,
  "nl-NL": nl_NL_default,
  "pl-PL": pl_PL_default,
  "pt-BR": pt_BR_default,
  "ro-RO": ro_RO_default,
  "ru-RU": ru_RU_default,
  "th-TH": th_TH_default,
  "tr-TR": tr_TR_default,
  "uk-UA": uk_UA_default,
  "vi-VN": vi_VN_default,
  "zh-CN": zh_CN_default,
  "zh-TW": zh_TW_default
};
function i18n(locale) {
  return locales[locale] || en_US_default;
}

// src/components/styles/wikicommit-explorer.scss
var wikicommit_explorer_default = "@media all and (max-width: 800px) {\n  .page > #quartz-body > :not(.sidebar.left:has(.explorer)) {\n    transition: transform 300ms ease-in-out;\n  }\n  .page > #quartz-body.lock-scroll > :not(.sidebar.left:has(.explorer)) {\n    transform: translateX(100dvw);\n    transition: transform 300ms ease-in-out;\n  }\n  .page > #quartz-body .sidebar.left:has(.explorer) {\n    box-sizing: border-box;\n    position: sticky;\n    background-color: var(--light);\n    padding: 1rem 0 1rem 0;\n    margin: 0;\n  }\n  .page > #quartz-body .hide-until-loaded ~ .explorer-content {\n    display: none;\n  }\n}\n.explorer {\n  display: flex;\n  flex-direction: column;\n  overflow-y: hidden;\n  min-height: 1.2rem;\n  flex: 0 1 auto;\n}\n\n.explorer.collapsed {\n  flex: 0 1 1.2rem;\n}\n\n.explorer.collapsed .fold {\n  transform: rotateZ(-90deg);\n}\n\n.explorer .fold {\n  margin-left: 0.5rem;\n  transition: transform 0.3s ease;\n  opacity: 0.8;\n}\n\n@media all and (max-width: 800px) {\n  .explorer {\n    order: -1;\n    height: initial;\n    overflow: hidden;\n    flex-shrink: 0;\n    align-self: flex-start;\n    margin-top: auto;\n    margin-bottom: auto;\n  }\n}\n.explorer button.mobile-explorer {\n  display: none;\n}\n\n.explorer button.desktop-explorer {\n  display: flex;\n}\n\n@media all and (max-width: 800px) {\n  .explorer button.mobile-explorer {\n    display: flex;\n  }\n  .explorer button.desktop-explorer {\n    display: none;\n  }\n}\n.explorer svg {\n  pointer-events: all;\n  transition: transform 0.35s ease;\n}\n\n.explorer svg > polyline {\n  pointer-events: none;\n}\n\nbutton.mobile-explorer,\nbutton.desktop-explorer {\n  background-color: transparent;\n  border: none;\n  text-align: left;\n  cursor: pointer;\n  padding: 0;\n  color: var(--dark);\n  display: flex;\n  align-items: center;\n}\n\nbutton.mobile-explorer h2,\nbutton.desktop-explorer h2 {\n  font-size: 1rem;\n  display: inline-block;\n  margin: 0;\n}\n\n.explorer-content {\n  list-style: none;\n  overflow: hidden;\n  overflow-y: auto;\n  margin-top: 0.5rem;\n}\n\n.explorer-content ul {\n  list-style: none;\n  margin: 0;\n  padding: 0;\n}\n\n.explorer-content ul.explorer-ul {\n  overscroll-behavior: contain;\n}\n\n.explorer-content ul li > a {\n  color: var(--dark);\n  opacity: 0.75;\n  pointer-events: all;\n}\n\n.explorer-content ul li > a.active {\n  opacity: 1;\n  color: var(--tertiary);\n}\n\n.explorer-content .folder-outer {\n  visibility: collapse;\n  display: grid;\n  grid-template-rows: 0fr;\n  transition-property: grid-template-rows, visibility;\n  transition-duration: 0.3s;\n  transition-timing-function: ease-in-out;\n}\n\n.explorer-content .folder-outer.open {\n  visibility: visible;\n  grid-template-rows: 1fr;\n}\n\n.explorer-content .folder-outer > ul {\n  overflow: hidden;\n  margin-left: 6px;\n  padding-left: 0.8rem;\n  border-left: 1px solid var(--lightgray);\n}\n\n.folder-container {\n  flex-direction: row;\n  display: flex;\n  align-items: center;\n  user-select: none;\n}\n\n.folder-container div > a {\n  color: var(--secondary);\n  font-family: var(--headerFont);\n  font-size: 0.95rem;\n  font-weight: 600;\n  line-height: 1.5rem;\n  display: inline-block;\n}\n\n.folder-container div > a:hover {\n  color: var(--tertiary);\n}\n\n.folder-container div > button {\n  color: var(--dark);\n  background-color: transparent;\n  border: none;\n  text-align: left;\n  cursor: pointer;\n  padding-left: 0;\n  padding-right: 0;\n  display: flex;\n  align-items: center;\n  font-family: var(--headerFont);\n}\n\n.folder-container div > button span {\n  font-size: 0.95rem;\n  display: inline-block;\n  color: var(--secondary);\n  font-weight: 600;\n  margin: 0;\n  line-height: 1.5rem;\n  pointer-events: none;\n}\n\n.folder-icon {\n  margin-right: 5px;\n  color: var(--secondary);\n  cursor: pointer;\n  transition: transform 0.3s ease;\n  backface-visibility: visible;\n  flex-shrink: 0;\n}\n\nli:has(> .folder-outer:not(.open)) > .folder-container > svg {\n  transform: rotate(-90deg);\n}\n\n.folder-icon:hover {\n  color: var(--tertiary);\n}\n\n@media all and (max-width: 800px) {\n  .explorer.collapsed {\n    flex: 0 0 34px;\n  }\n  .explorer.collapsed > .explorer-content {\n    transform: translateX(-100vw);\n    visibility: hidden;\n  }\n  .explorer:not(.collapsed) {\n    flex: 0 0 34px;\n  }\n  .explorer:not(.collapsed) > .explorer-content {\n    transform: translateX(0);\n    visibility: visible;\n  }\n  .explorer .explorer-content {\n    box-sizing: border-box;\n    z-index: 100;\n    position: absolute;\n    top: 0;\n    left: 0;\n    margin-top: 0;\n    background-color: var(--light);\n    max-width: 100vw;\n    width: 100vw;\n    transform: translateX(-100vw);\n    transition: transform 200ms ease, visibility 200ms ease;\n    overflow: hidden;\n    padding: 4rem 0 2rem 0;\n    height: 100dvh;\n    max-height: 100dvh;\n    visibility: hidden;\n  }\n  .explorer .mobile-explorer {\n    margin: 0;\n    padding: 5px;\n    z-index: 101;\n  }\n  .explorer .mobile-explorer.hide-until-loaded {\n    display: none;\n  }\n  .explorer .mobile-explorer .lucide-menu {\n    stroke: var(--darkgray);\n  }\n}\n@media all and (max-width: 800px) {\n  .mobile-no-scroll .explorer-content > .explorer-ul {\n    overscroll-behavior: contain;\n  }\n}";

// src/components/scripts/wikicommit-explorer.inline.ts
var wikicommit_explorer_inline_default = `var Z=Object.hasOwnProperty;function S(u){let e=O(j(u,"index"),!0);return e.length===0?"/":e}function W(){return typeof document>"u"?"":document.body?.dataset?.basepath??""}function v(u,e){let t=e??W(),n=u.startsWith("/")?u:"/"+u;return t+n}function R(u,e){return u===e||u.endsWith("/"+e)}function j(u,e){return R(u,e)&&(u=u.slice(0,-e.length)),u}function O(u,e){return u.startsWith("/")&&(u=u.substring(1)),!e&&u.endsWith("/")&&(u=u.slice(0,-1)),u}var N=/^[a-z]{2}$/;function G(u){let e=u.split("/")[0]??"";return N.test(e)?e:null}function _(u){let e=[];return u.forEach((t,n)=>{t.isFolder&&t.slugSegment!==void 0&&N.test(t.slugSegment)&&e.push(n)}),e.length!==1?-1:e[0]??-1}function L(u,e,t){let n=G(e),r=n?u.children.findIndex(D=>D.isFolder&&D.slugSegment===n):_(u.children);if(r===-1)return;let F=u.children[r];F&&(u.children.splice(r,1,...F.children),t&&u.children.sort(t))}var H="#group-";function w(u,e,t){if(!t||typeof t!="object"||!t.folders)return null;let n=u.split("/");if(n.length<2)return null;let r=n[n.length-1]??"";if(r==="index")return null;let F=n.slice(0,-1),D=t.folders[F.join("/")],c=D?.pages?.[r];if(!D||!c)return null;let A=D.groups?.[c]||c,a=H+c,l=(e||u).split("/"),d=[...l.slice(0,-1),a,l[l.length-1]??r];return{path:[...F,a,r],hintParts:d,label:A}}var b=class u{constructor(e,t){this.children=[],this.slugSegments=e,this.data=t||null,this.isFolder=!1,this.fileSegmentHint=null,this.displayNameOverride=void 0}get displayName(){return this.displayNameOverride!==void 0?this.displayNameOverride:(this.data?.title==="index"?void 0:this.data?.title)||this.fileSegmentHint||this.slugSegment||""}set displayName(e){this.displayNameOverride=e}get slug(){let e=this.slugSegments.join("/");return this.isFolder?e+"/index":e}get slugSegment(){return this.slugSegments[this.slugSegments.length-1]||""}makeChild(e,t){let n=[...this.slugSegments,e[0]],r=new u(n,t);return this.children.push(r),r}insert(e,t,n){if(e.length===0)return;this.isFolder=!0;let r=e[0];if(e.length===1)r==="index"?this.data||(this.data=t):this.makeChild(e,t);else{let F=this.children.find(c=>c.slugSegment===r);F||(F=this.makeChild(e,void 0));let D=n||(t.filePath||t.slug||"").split("/");F.fileSegmentHint=D[D.length-e.length],F.insert(e.slice(1),t,n)}}add(e,t){let n=w(e.slug,e.filePath,t);if(!n){this.insert(e.slug.split("/"),e);return}this.insert(n.path,e,n.hintParts);let r=this;for(let F of n.path.slice(0,-1))if(r=r.children.find(D=>D.slugSegment===F),!r)return;r.isGroup=!0,r.displayNameOverride=n.label}sort(e){this.children.sort(e),this.children.forEach(t=>t.sort(e))}filter(e){this.children=this.children.filter(e),this.children.forEach(t=>t.filter(e))}map(e){e(this),this.children.forEach(t=>t.map(e))}static fromEntries(e,t){let n=new u([],null);return e.forEach(([,r])=>n.add(r,t)),n}},q=(u,e)=>{let t=/^[a-z]{2}$/,n=D=>D.isFolder&&D.slugSegment==="sources"&&(D.slugSegments?.length??0)===1?2:D.isFolder&&t.test(D.slugSegment||"")?1:D.isFolder&&D.slugSegment==="overview"&&(D.slugSegments?.length??0)===1?-2:D.isFolder&&D.slugSegment==="view"?-1:0,r=n(u),F=n(e);return r!==F?r-F:!u.isFolder&&!e.isFolder||u.isFolder&&e.isFolder?u.displayName.localeCompare(e.displayName,void 0,{numeric:!0,sensitivity:"base"}):!u.isFolder&&e.isFolder?1:-1},$=u=>u.slugSegment!=="tags";function M(u,e,t,n,r){return t&&u.filter(t),n&&u.map(n),e&&u.sort(e),L(u,r,e),u}var y=null;function U(){return y||(y=fetch(v("wikicommit-groups.json")).then(u=>u.ok?u.json():null).catch(()=>null)),y}async function J(u,e){try{console.log("[Explorer] Fetching content index...");let t=await fetchData;if(console.log("[Explorer] Fetched data keys:",Object.keys(t).slice(0,5)),!t)return console.error("[Explorer] No data received"),null;let n=t.content||t,r=Object.entries(n);if(console.log("[Explorer] Entry count:",r.length),r.length===0)return console.warn("[Explorer] No content entries found"),null;let F=await U(),D=b.fromEntries(r,F);console.log("[Explorer] Trie root children:",D.children.length);let c=q,A=$,a=null;if(u)try{let l=JSON.parse(u);l.sortFn&&(c=new Function("a","b","return ("+l.sortFn+")(a, b)")),l.filterFn&&(A=new Function("node","return ("+l.filterFn+")(node)")),l.mapFn&&(a=new Function("node","("+l.mapFn+")(node)"))}catch(l){console.error("Error parsing data functions:",l)}return M(D,c,A,a,e)}catch(t){return console.error("Error building file trie:",t),null}}var P=0;function T(u,e,t,n,r,F=""){let D=document.getElementById("template-folder"),c=document.getElementById("template-file");if(!D||!c)return;let A=F?F+"/"+u.slugSegment:u.slugSegment,a=S(t);if(u.isFolder){let l=D.content.cloneNode(!0),d=l.querySelector(".folder-container"),p=l.querySelector(".folder-button"),m=l.querySelector(".folder-title"),i=l.querySelector(".folder-outer"),s=l.querySelector(".content");if(m&&(m.textContent=u.displayName||u.slugSegment),d&&(d.dataset.folderpath=u.slug),n==="link"&&p&&!u.isGroup){let o=document.createElement("a");o.className=p.className;let g=S(u.slug);o.href=v(g||""),m?o.appendChild(m):o.textContent=u.displayName||u.slugSegment,p.replaceWith(o),p=o}let C=r[u.slug]!==void 0?r[u.slug]:!0,E=S(u.slug),f=E&&E===a.slice(0,E.length)||u.isGroup&&u.children.some(o=>o.data&&o.data.slug===t);if((!C||f)&&i&&i.classList.add("open"),u.children&&u.children.length>0&&s)for(let o of u.children)T(o,s,t,n,r,A);e.appendChild(l)}else if(u.data){let l=c.content.cloneNode(!0),d=l.querySelector("a");d&&(d.href=v(u.data.slug),d.textContent=u.displayName||u.slugSegment,u.data.slug===t&&d.classList.add("active","is-active")),e.appendChild(l)}}async function I(u){let e=++P;try{console.log("[Explorer] Nav event received, generation:",e);let t=(u.detail?.url||"").replace(/^\\/+/,""),n=document.querySelectorAll("div.explorer");console.log("[Explorer] Found",n.length,"explorers");let r={};try{JSON.parse(localStorage.getItem("fileTree")||"[]").forEach(D=>{r[D.path]=D.collapsed})}catch(F){console.error("[Explorer] Error loading saved state:",F)}for(let F of n){let D=F.querySelector(".explorer-ul");if(!D){console.warn("[Explorer] No explorer-ul found");continue}D.innerHTML='<li class="overflow-end"></li>';let c=F.dataset.dataFns,A=F.dataset.behavior||"collapse";console.log("[Explorer] Starting tree build...");let a=await J(c,t);if(e===P){if(console.log("[Explorer] Render generation is current, rendering tree"),console.log("[Explorer] Trie result:",a?"success":"null"),a&&a.children&&a.children.length>0){D.innerHTML='<li class="overflow-end"></li>',console.log("[Explorer] Rendering",a.children.length,"children");for(let s of a.children)T(s,D,t,A,r,"");console.log("[Explorer] Render complete, final list length:",D.children.length)}else console.warn("[Explorer] No trie or empty children");let i=sessionStorage.getItem("explorerScrollTop");if(i)D.scrollTop=parseInt(i,10);else{let s=D.querySelector(".active");s&&s.scrollIntoView({behavior:"smooth"})}}else console.log("[Explorer] Stale render generation, skipping tree render");let l=[],d=F.getElementsByClassName("explorer-toggle");for(let i of d){let s=function(){let C=this.closest(".explorer");if(!C)return;let E=C.classList.toggle("collapsed");C.setAttribute("aria-expanded",E?"false":"true"),E?document.documentElement.classList.remove("mobile-no-scroll"):document.documentElement.classList.add("mobile-no-scroll")};i.addEventListener("click",s),l.push(()=>i.removeEventListener("click",s))}let p=F.getElementsByClassName("folder-icon");for(let i of p){let s=function(C){C.stopPropagation();let E=this.parentElement;if(!E)return;let f=E.nextElementSibling;if(!f)return;f.classList.toggle("open");let o=!f.classList.contains("open"),g=E.dataset.folderpath,B=JSON.parse(localStorage.getItem("fileTree")||"[]"),h=B.findIndex(x=>x.path===g);h>=0?B[h].collapsed=o:B.push({path:g,collapsed:o}),localStorage.setItem("fileTree",JSON.stringify(B))};i.addEventListener("click",s),l.push(()=>i.removeEventListener("click",s))}let m=F.getElementsByClassName("folder-button");for(let i of m){let s=function(C){let E=this.closest(".folder-container");if(!E)return;let f=F.dataset.behavior||"collapse",o=E.nextElementSibling,g=E.dataset.folderpath;if(f!=="link"){if(C.stopPropagation(),!o)return;o.classList.toggle("open");let B=!o.classList.contains("open"),h=JSON.parse(localStorage.getItem("fileTree")||"[]"),x=h.findIndex(k=>k.path===g);x>=0?h[x].collapsed=B:h.push({path:g,collapsed:B}),localStorage.setItem("fileTree",JSON.stringify(h))}};i.addEventListener("click",s),l.push(()=>i.removeEventListener("click",s))}typeof window<"u"&&window.addCleanup&&window.addCleanup(()=>l.forEach(i=>i()))}for(let F of document.getElementsByClassName("explorer")){let D=F.querySelector(".mobile-explorer");D&&(D.classList.remove("hide-until-loaded"),D.checkVisibility&&D.checkVisibility()&&(F.classList.add("collapsed"),F.setAttribute("aria-expanded","false"),document.documentElement.classList.remove("mobile-no-scroll")))}}catch(t){console.error("[Explorer] Fatal error in nav handler:",t)}}document.addEventListener("nav",I);document.addEventListener("render",I);document.addEventListener("prenav",()=>{let u=document.querySelector(".explorer-ul");u&&sessionStorage.setItem("explorerScrollTop",u.scrollTop.toString())});
`;

// src/components/WikiCommitExplorer.tsx
var explorerSortFn = (a2, b2) => {
  const LANG_SEGMENT_RE = /^[a-z]{2}$/;
  const sortTier = (n2) => {
    if (n2.isFolder && n2.slugSegment === "sources" && (n2.slugSegments?.length ?? 0) === 1) {
      return 2;
    }
    if (n2.isFolder && LANG_SEGMENT_RE.test(n2.slugSegment || "")) {
      return 1;
    }
    if (n2.isFolder && n2.slugSegment === "overview" && (n2.slugSegments?.length ?? 0) === 1) {
      return -2;
    }
    if (n2.isFolder && n2.slugSegment === "view") {
      return -1;
    }
    return 0;
  };
  const aTier = sortTier(a2);
  const bTier = sortTier(b2);
  if (aTier !== bTier) {
    return aTier - bTier;
  }
  if (!a2.isFolder && !b2.isFolder || a2.isFolder && b2.isFolder) {
    return (a2.displayName || "").localeCompare(b2.displayName || "", void 0, {
      numeric: true,
      sensitivity: "base"
    });
  }
  if (!a2.isFolder && b2.isFolder) {
    return 1;
  }
  return -1;
};
var defaultOptions = {
  folderDefaultState: "collapsed",
  folderClickBehavior: "link",
  useSavedState: true,
  mapFn: (node) => {
    return node;
  },
  sortFn: explorerSortFn,
  filterFn: (node) => node.slugSegment !== "tags",
  order: ["filter", "map", "sort"]
};
var numExplorers = 0;
function concatenateResources(...resources) {
  return resources.filter((r2) => !!r2).join("\n");
}
var WikiCommitExplorer_default = ((userOpts) => {
  const opts = { ...defaultOptions, ...userOpts };
  const { OverflowList: OverflowList2, overflowListAfterDOMLoaded } = OverflowList_default();
  const WikiCommitExplorer = (props) => {
    const { cfg } = props;
    const displayClass = props.displayClass;
    const id = `explorer-${numExplorers++}`;
    const locale = cfg?.locale ?? "en-US";
    const title = opts.title ?? i18n(locale).components.explorer.title;
    return /* @__PURE__ */ u2(
      "div",
      {
        class: classNames(displayClass, "explorer", "nav-files-container"),
        "data-behavior": opts.folderClickBehavior,
        "data-collapsed": opts.folderDefaultState,
        "data-savestate": opts.useSavedState,
        "data-data-fns": JSON.stringify({
          order: opts.order,
          sortFn: opts.sortFn?.toString(),
          filterFn: opts.filterFn?.toString(),
          mapFn: opts.mapFn?.toString()
        }),
        children: [
          /* @__PURE__ */ u2(
            "button",
            {
              type: "button",
              class: "explorer-toggle mobile-explorer hide-until-loaded",
              "data-mobile": true,
              "aria-controls": id,
              "aria-label": i18n(cfg?.locale ?? "en-US").components.explorer.title,
              children: /* @__PURE__ */ u2(
                "svg",
                {
                  xmlns: "http://www.w3.org/2000/svg",
                  width: "24",
                  height: "24",
                  viewBox: "0 0 24 24",
                  "stroke-width": "2",
                  "stroke-linecap": "round",
                  "stroke-linejoin": "round",
                  class: "lucide-menu",
                  children: [
                    /* @__PURE__ */ u2("line", { x1: "4", x2: "20", y1: "12", y2: "12" }),
                    /* @__PURE__ */ u2("line", { x1: "4", x2: "20", y1: "6", y2: "6" }),
                    /* @__PURE__ */ u2("line", { x1: "4", x2: "20", y1: "18", y2: "18" })
                  ]
                }
              )
            }
          ),
          /* @__PURE__ */ u2(
            "button",
            {
              type: "button",
              class: "title-button explorer-toggle desktop-explorer",
              "data-mobile": false,
              "aria-expanded": true,
              children: [
                /* @__PURE__ */ u2("h2", { children: title }),
                /* @__PURE__ */ u2(
                  "svg",
                  {
                    xmlns: "http://www.w3.org/2000/svg",
                    width: "14",
                    height: "14",
                    viewBox: "5 8 14 8",
                    fill: "none",
                    stroke: "currentColor",
                    "stroke-width": "2",
                    "stroke-linecap": "round",
                    "stroke-linejoin": "round",
                    class: "fold",
                    children: /* @__PURE__ */ u2("polyline", { points: "6 9 12 15 18 9" })
                  }
                )
              ]
            }
          ),
          /* @__PURE__ */ u2("div", { id, class: "explorer-content", "aria-expanded": false, role: "group", children: /* @__PURE__ */ u2(OverflowList2, { class: "explorer-ul" }) }),
          /* @__PURE__ */ u2("template", { id: "template-file", children: /* @__PURE__ */ u2("li", { children: /* @__PURE__ */ u2("a", { href: "#", class: "nav-file-title tree-item-self" }) }) }),
          /* @__PURE__ */ u2("template", { id: "template-folder", children: /* @__PURE__ */ u2("li", { children: [
            /* @__PURE__ */ u2("div", { class: "folder-container nav-folder-title tree-item-self", children: [
              /* @__PURE__ */ u2(
                "svg",
                {
                  xmlns: "http://www.w3.org/2000/svg",
                  width: "12",
                  height: "12",
                  viewBox: "5 8 14 8",
                  fill: "none",
                  stroke: "currentColor",
                  "stroke-width": "2",
                  "stroke-linecap": "round",
                  "stroke-linejoin": "round",
                  class: "folder-icon nav-folder-collapse-indicator collapse-icon",
                  children: /* @__PURE__ */ u2("polyline", { points: "6 9 12 15 18 9" })
                }
              ),
              /* @__PURE__ */ u2("div", { children: /* @__PURE__ */ u2("button", { class: "folder-button", children: /* @__PURE__ */ u2("span", { class: "folder-title" }) }) })
            ] }),
            /* @__PURE__ */ u2("div", { class: "folder-outer", children: /* @__PURE__ */ u2("ul", { class: "content tree-item-children" }) })
          ] }) })
        ]
      }
    );
  };
  WikiCommitExplorer.css = wikicommit_explorer_default;
  WikiCommitExplorer.afterDOMLoaded = concatenateResources(wikicommit_explorer_inline_default, overflowListAfterDOMLoaded);
  return WikiCommitExplorer;
});

export { WikiCommitExplorer_default as WikiCommitExplorer };
//# sourceMappingURL=index.js.map
//# sourceMappingURL=index.js.map