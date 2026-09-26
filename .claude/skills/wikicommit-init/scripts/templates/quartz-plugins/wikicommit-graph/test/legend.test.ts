import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { i18n } from "../src/i18n";
import { classifyNode } from "../src/util/nodeFilter";

const LOCALES_DIR = join(import.meta.dirname, "..", "src", "i18n", "locales");
const SCSS = readFileSync(
  join(import.meta.dirname, "..", "src", "components", "styles", "graph.scss"),
  "utf-8",
);
// Read the source rather than `Graph({}).afterDOMLoaded`: vitest aliases the
// inline script to a stub (the real one is only assembled by the esbuild
// loader at build time), so the component would hand back the stub here.
const INLINE = readFileSync(
  join(import.meta.dirname, "..", "src", "components", "scripts", "graph.inline.ts"),
  "utf-8",
);

// Issue #841: sources were drawn exactly like entity pages, and nothing said
// what the shapes already in use meant. Shape carries the kind and colour
// carries the visit state; these tests hold both halves of that in place.
describe("node legend", () => {
  const NEW_KEYS = [
    "legend",
    "legendPages",
    "legendCurrent",
    "legendVisited",
    "legendUnvisited",
    // Issue #984: the two hints the swatches cannot carry.
    "legendVisitedHint",
    "legendTagsAlways",
  ];

  it("every locale carries the legend labels", () => {
    // `Record<string, typeof enUS>` already makes a missing key a type error,
    // but not an empty string — and an empty caption renders as a blank line
    // rather than as anything a reader can act on.
    const codes = readdirSync(LOCALES_DIR)
      .filter((f) => f.endsWith(".ts"))
      .map((f) => f.replace(/\.ts$/, ""));
    expect(codes.length).toBeGreaterThan(1);

    for (const code of codes) {
      const controls = i18n(code).components.graph.controls as Record<string, string>;
      for (const key of NEW_KEYS) {
        expect(controls[key], `${code}.${key}`).toBeTruthy();
      }
    }
  });

  it("reuses the labels the bar already had for tags and sources", () => {
    // Those two name the same things the Sources/Tags toggles do, so a second
    // wording for either would be two names for one thing in one bar.
    const controls = i18n("en-US").components.graph.controls;
    expect(controls.tags).toBeTruthy();
    expect(controls.sources).toBeTruthy();
  });

  it("falls back to English for a locale nobody translated", () => {
    expect(i18n("xx-XX").components.graph.controls.legend).toBe(
      i18n("en-US").components.graph.controls.legend,
    );
  });
});

describe("node shape encodes the kind", () => {
  it("classifyNode separates the three kinds the legend names", () => {
    expect(classifyNode("tags/ml").kind).toBe("tag");
    expect(classifyNode("sources/url/example.com/article").kind).toBe("source");
    expect(classifyNode("ja/Person/yamada-taro").kind).toBe("entity");
  });

  it("the inline script decides the shape from classifyNode, not from a prefix", () => {
    // The drawing code used to re-derive "is this a tag" with its own
    // `startsWith("tags/")` rather than ask the classifier the same file
    // already pulled the rest of nodeFilter from. That second copy is what let
    // sources go unnoticed: it had no case for them.
    // The import too, not just the call: the file carries `@ts-nocheck` and is
    // outside eslint's scope, so calling an unimported helper compiles, bundles
    // and ships — and then throws on the first node drawn.
    expect(INLINE).toMatch(
      /^import \{[^}]*\bclassifyNode\b[^}]*\} from "\.\.\/\.\.\/util\/nodeFilter";$/m,
    );
    expect(INLINE).toContain("classifyNode(nodeId).kind");
    expect(INLINE).not.toContain('nodeId.startsWith("tags/")');
    expect(INLINE).not.toContain('d.id.startsWith("tags/")');
  });

  it("draws sources as squares and keeps tags hollow", () => {
    expect(INLINE).toContain("isSourceNode");
    expect(INLINE).toMatch(/gfx\.rect\(/);
    expect(INLINE).toMatch(/gfx\.circle\(/);
  });
});

describe("legend swatches", () => {
  it("use the same three theme colours the graph does", () => {
    // Not fresh colours of the fork's own: the theme exposes two accents plus
    // grey, and a swatch outside that set would stop matching the graph the
    // moment a user changed their theme.
    for (const variable of ["--secondary", "--tertiary", "--gray", "--light"]) {
      expect(SCSS, variable).toContain(`global-graph-controls__legend-swatch`);
      expect(SCSS).toContain(variable);
    }
  });

  it("gives no two legend items the same mark", () => {
    // "Pages" and "Not visited" were both a plain grey circle, so the two
    // halves of the legend collided on their most ordinary entry each. The
    // shape half uses --darkgray, which is deliberately not one of the three
    // state colours.
    const block = SCSS.slice(SCSS.indexOf("__legend-swatch"));
    function rule(modifier: string) {
      const start = block.indexOf(`&--${modifier}`);
      expect(start, modifier).toBeGreaterThan(-1);
      return block.slice(start, block.indexOf("}", start));
    }
    expect(rule("entity")).toContain("--darkgray");
    expect(rule("source")).toContain("--darkgray");
    expect(rule("unvisited")).toContain("var(--gray)");
    expect(rule("entity")).not.toContain("var(--gray)");
  });

  it("keeps the visit-state swatches round", () => {
    // Shape means kind. A square "visited" swatch would read as a fourth kind.
    const block = SCSS.slice(SCSS.indexOf("__legend-swatch"));
    const sourceRule = block.slice(block.indexOf("&--source"));
    expect(sourceRule).toContain("border-radius: 0");
    expect(block.slice(block.indexOf("&--current"))).not.toContain("border-radius: 0");
  });
});

// Issue #984: the legend named a colour "Visited" without saying what counts as
// a visit, and tags are drawn in that colour whether or not they have been
// opened — so for tags the label was simply untrue. Both gaps are closed with
// `title` hints rather than prose, because the legend's shape (six items in two
// groups, Issue #841) and the bar's height (Issue #838) are both already spent.
describe("the legend explains what the colours cannot", () => {
  it("says tags always use that colour, independent of the visit state", () => {
    // The exception is in the drawing code, so the legend has to carry it: a
    // reader with Tags on otherwise sees 100+ never-opened tags in the colour
    // the legend calls "Visited".
    expect(INLINE).toContain('classifyNode(d.id).kind === "tag"');
    expect(INLINE).toContain("labels.legendTagsAlways");
    const hint = i18n("en-US").components.graph.controls.legendTagsAlways;
    expect(hint).toMatch(/tags/i);
    expect(hint).toMatch(/whether or not/i);
  });

  it("defines Visited as this browser, not a server-side or wiki-wide record", () => {
    // `graph-visited` is a localStorage key. It is not the session, not other
    // readers, not `review_status` — and every one of those is a direction a
    // reader could guess wrong.
    expect(INLINE).toContain("labels.legendVisitedHint");
    expect(i18n("en-US").components.graph.controls.legendVisitedHint).toMatch(/browser/i);
  });

  it("keeps the hint on title rather than adding a seventh legend item", () => {
    // Six items in two groups is the shape Issue #841 settled on; a hint that
    // rendered as its own item would read as a fourth kind or a fourth state.
    expect(INLINE).toContain("if (hint) item.title = hint;");
  });
});

// Issue #984: one caption over two identical number boxes said nothing about
// which end was which, and the only hint was a hardcoded-English `title`.
describe("the degree range labels its two ends", () => {
  it("gives each input its own visible caption", () => {
    expect(INLINE).toContain("labels.degreeMin");
    expect(INLINE).toContain("labels.degreeMax");
    expect(INLINE).toContain("global-graph-controls__range-item");
  });

  it("no longer hardcodes the bound hint in English", () => {
    expect(INLINE).not.toContain('"0 = no lower bound"');
    expect(INLINE).not.toContain('"0 = no upper bound"');
    expect(INLINE).toContain("labels.degreeNoBound");
  });

  it("carries the three degree labels in every locale", () => {
    const codes = readdirSync(LOCALES_DIR)
      .filter((f) => f.endsWith(".ts"))
      .map((f) => f.replace(/\.ts$/, ""));
    for (const code of codes) {
      const controls = i18n(code).components.graph.controls as Record<string, string>;
      for (const key of ["degreeMin", "degreeMax", "degreeNoBound"]) {
        expect(controls[key], `${code}.${key}`).toBeTruthy();
      }
    }
  });

  it("spells the bound value the way the input shows it", () => {
    // The hint names a literal the reader sees and types, and `input.value` is
    // `String(0)` — an ASCII zero — in every locale. A localised digit (the
    // Persian ۰ was the one that slipped in) would name a character that never
    // appears in the box it is describing.
    const codes = readdirSync(LOCALES_DIR)
      .filter((f) => f.endsWith(".ts"))
      .map((f) => f.replace(/\.ts$/, ""));
    for (const code of codes) {
      const controls = i18n(code).components.graph.controls as Record<string, string>;
      expect(controls.degreeNoBound, `${code}.degreeNoBound`).toContain("0");
    }
  });

  it("keeps the caret guard: sync writes only when the string differs", () => {
    // The guard exists because `change` can fire on Enter with the field still
    // focused, and assigning `value` resets the caret in some engines. Relabel
    // the inputs, not the write-back (Issue #651's {field, sync} contract).
    expect(INLINE).toContain("if (minInput.value !== nextMin) minInput.value = nextMin;");
    expect(INLINE).toContain("if (maxInput.value !== nextMax) maxInput.value = nextMax;");
  });

  it("does not nest a label inside a label", () => {
    // Each end is its own <label>, so the wrapper had to stop being one.
    const fn = INLINE.slice(
      INLINE.indexOf("function buildDegreeRange"),
      INLINE.indexOf("function buildLegend"),
    );
    expect(fn).toContain('var wrapper = document.createElement("div");');
  });
});

// Issue #985: the legend's "Sources" and "Tags" rows repeated the two toggles
// of the same name, so one bar said each word twice — once pressable, once not.
// The marks moved into the toggles; the legend kept only what has no toggle.
describe("the Sources / Tags marks live on their toggles, not in the legend", () => {
  const legendFn = INLINE.slice(
    INLINE.indexOf("function buildLegend"),
    INLINE.indexOf("function renderControls"),
  );
  const toggleFn = INLINE.slice(
    INLINE.indexOf("function buildToggle("),
    INLINE.indexOf("function buildDegreeRange"),
  );

  it("drops the tag and source rows from the legend", () => {
    expect(legendFn).not.toMatch(/addItem\(\s*"tag"/);
    expect(legendFn).not.toMatch(/addItem\(\s*"source"/);
    // "Pages" has no toggle — turning pages off would empty the graph through
    // the prune — so its mark stays in the legend.
    expect(legendFn).toMatch(/addItem\("entity"/);
  });

  it("keeps the legend non-interactive", () => {
    // Moving the marks is what spared the legend from having two pressable
    // rows beside four that are not.
    expect(legendFn).not.toContain('createElement("button")');
    expect(legendFn).not.toContain("addEventListener");
  });

  it("puts an aria-hidden swatch inside the toggle, reusing the legend's class", () => {
    // Same class as the legend, so the two marks cannot be restyled apart; and
    // hidden from assistive technology, so the button reads as its label only.
    expect(toggleFn).toContain(
      '"global-graph-controls__legend-swatch global-graph-controls__legend-swatch--" +',
    );
    expect(toggleFn).toContain('mark.setAttribute("aria-hidden", "true")');
    // The label is appended as a text node after the mark; assigning
    // textContent would wipe the swatch out.
    expect(toggleFn).not.toContain("button.textContent");
    expect(toggleFn).toContain("button.appendChild(document.createTextNode(labelText))");
  });

  it("gives Sources the square and Tags the hollow circle, with the tag hint", () => {
    expect(INLINE).toMatch(/\{ modifier: "source" \}/);
    expect(INLINE).toMatch(/modifier: "tag",\s*hint:\s*labels\.legendTagsAlways/);
  });

  it("rings the source swatch on a pressed toggle with a theme variable", () => {
    const pressed = SCSS.slice(SCSS.indexOf('&[aria-pressed="true"]'));
    const ring = pressed.slice(pressed.indexOf("__legend-swatch--source"));
    expect(ring).toMatch(/box-shadow:\s*0 0 0 1px var\(--light\)/);
  });
});
