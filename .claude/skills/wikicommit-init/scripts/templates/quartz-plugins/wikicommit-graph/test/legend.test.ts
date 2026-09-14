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
  const NEW_KEYS = ["legend", "legendPages", "legendCurrent", "legendVisited", "legendUnvisited"];

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
