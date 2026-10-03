import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import {
  DEFAULT_LABEL_LIMIT,
  type LabelCandidate,
  labelAlpha,
  normalizeLabelLimit,
  restingLabelAlpha,
  selectLabels,
  zoomLabelAlpha,
} from "./labelOpacity";
import { i18n } from "../i18n";

const INLINE = readFileSync(
  join(import.meta.dirname, "..", "components", "scripts", "graph.inline.ts"),
  "utf-8",
);

// Issue #986: nodes and links split 1 / 0.2 on `active` while a node was
// hovered, and the labels never joined in. On a 969-node graph that meant
// hovering told you which nodes were connected but not what any of them were
// called, and the only way to read a name was to zoom until every label in the
// graph came up at once.
describe("labelAlpha", () => {
  it("raises the hovered node's own label", () => {
    expect(labelAlpha(true, true, true, 0)).toBe(1);
  });

  it("raises the hovered node's neighbours, which is what was missing", () => {
    expect(labelAlpha(false, true, true, 0)).toBe(1);
  });

  it("drops everything else to 0 while focusing", () => {
    // Not to the 0.2 the nodes and links use: a dot at 0.2 still gives the
    // graph its shape, text at 0.2 is unreadable overlap.
    expect(labelAlpha(false, false, true, 0)).toBe(0);
  });

  it("drops non-neighbours even when the zoom would have shown them", () => {
    // The old zoom handler wrote one scale-derived value onto every label that
    // was not active, so zoomed in, hovering changed nothing about the labels.
    expect(labelAlpha(false, false, true, 0.8)).toBe(0);
  });

  it("leaves the zoom in charge when nothing is focusing", () => {
    expect(labelAlpha(false, false, false, 0.4)).toBe(0.4);
    expect(labelAlpha(false, true, false, 0.4)).toBe(0.4);
  });

  it("still raises the hovered label with focusOnHover off", () => {
    // `focusing` is "hovered AND focusOnHover"; the hovered node's own label
    // was never gated on that flag upstream, so the hover branch comes first.
    expect(labelAlpha(true, false, false, 0)).toBe(1);
  });
});

describe("zoomLabelAlpha", () => {
  it("is 0 at the default scale, which is why an untouched graph has no labels", () => {
    expect(zoomLabelAlpha(1, 1)).toBe(0);
    expect(zoomLabelAlpha(0.9, 1)).toBe(0);
  });

  it("never goes negative", () => {
    expect(zoomLabelAlpha(0.1, 1)).toBe(0);
  });

  it("keeps upstream's ramp: full opacity at 4.75x", () => {
    // The curve is deliberately unchanged. What Issue #986 fixed is that hover
    // could not override it, not the shape of the ramp.
    expect(zoomLabelAlpha(4.75, 1)).toBeCloseTo(1);
    expect(zoomLabelAlpha(2.875, 1)).toBeCloseTo(0.5);
  });

  it("scales with opacityScale, so the config key still moves the ramp", () => {
    expect(zoomLabelAlpha(1, 4.75)).toBeCloseTo(1);
  });
});

describe("the inline script has one writer of label.alpha", () => {
  function body(name: string): string {
    const start = INLINE.indexOf("function " + name + "(");
    expect(start, name).toBeGreaterThan(-1);
    // Functions here are declared at a fixed indentation, so the next line that
    // closes at that indentation ends the body.
    const end = INLINE.indexOf("\n      }\n", start);
    expect(end, name).toBeGreaterThan(start);
    return INLINE.slice(start, end);
  }

  it("assigns label alpha in renderLabels and, once, at creation", () => {
    // Three places used to write it; that is the whole defect. A fourth writer
    // added later would reintroduce it silently, because each of the three was
    // individually reasonable. The creation default is the documented
    // exception: it is a starting value for the frames before the first render,
    // not a second opinion about what a label's opacity should be.
    const assignments = INLINE.match(/label(?:Ref)?\.alpha\s*=[^;]*/g) ?? [];
    expect(assignments).toHaveLength(2);
    expect(assignments.filter((a) => /=\s*0$/.test(a))).toHaveLength(1);
    expect(body("renderLabels")).toMatch(/label\.alpha\s*=/);
  });

  it("reads the same active flag renderNodes does", () => {
    expect(body("renderLabels")).toContain("nodeData.active");
    expect(body("renderNodes")).toContain("nodeData.active");
  });

  it("gates on focusOnHover, so the upstream behaviour is still reachable", () => {
    expect(body("renderLabels")).toContain("focusOnHover");
  });

  it("delegates the decision rather than restating it", () => {
    expect(INLINE).toMatch(
      /^import \{[^}]*\blabelAlpha\b[^}]*\} from "\.\.\/\.\.\/util\/labelOpacity";$/m,
    );
    // The ramp's constant lives in one place now. A second copy in the zoom
    // handler is how the two mechanisms drifted apart to begin with.
    expect(INLINE).not.toContain("3.75");
  });

  it("no longer saves and restores the hovered label's alpha by hand", () => {
    // That save/restore existed because nothing else put the hovered label back
    // down. It is now both unnecessary and unreachable — the restore ran and
    // was immediately overwritten by the following renderPixiFromD3().
    expect(INLINE).not.toContain("oldLabelOpacity");
  });

  it("lets the zoom handler ask for a redraw instead of writing labels itself", () => {
    // The replaced loop called activeLabels.indexOf() inside a walk of the
    // label container: ~1M comparisons per zoom or pan at 969 nodes.
    expect(INLINE).not.toContain("activeLabels");
  });
});

// Issue #1128: on a 1000-page wiki the zoom ramp alone filled the screen with
// text, and every zoom in between left all labels half transparent. The global
// graph now labels at most `labelLimit` nodes of those on screen.
describe("selectLabels", () => {
  const VIEW = { x0: -100, y0: -100, x1: 100, y1: 100 };
  function node(
    id: string,
    degree: number,
    opts: { x?: number | null; y?: number | null; secondary?: boolean } = {},
  ): LabelCandidate {
    return {
      id,
      x: opts.x === undefined ? 0 : opts.x,
      y: opts.y === undefined ? 0 : opts.y,
      degree,
      secondary: opts.secondary ?? false,
    };
  }

  it("returns null for limit 0, which hands the labels back to the zoom ramp", () => {
    expect(selectLabels([node("a", 1)], VIEW, 0)).toBeNull();
  });

  it("labels everything on screen while that fits under the limit", () => {
    const chosen = selectLabels(
      [node("a", 0), node("b", 5), node("t", 9, { secondary: true })],
      VIEW,
      3,
    );
    expect(chosen).toEqual(new Set(["a", "b", "t"]));
  });

  it("only counts what is on screen", () => {
    const chosen = selectLabels([node("in", 0), node("out", 99, { x: 500 })], VIEW, 1);
    expect(chosen).toEqual(new Set(["in"]));
  });

  it("treats the viewport edge as inside", () => {
    const chosen = selectLabels([node("edge", 0, { x: 100, y: -100 })], VIEW, 1);
    expect(chosen).toEqual(new Set(["edge"]));
  });

  it("skips nodes the simulation has not placed yet", () => {
    const chosen = selectLabels([node("a", 1, { x: null }), node("b", 0)], VIEW, 5);
    expect(chosen).toEqual(new Set(["b"]));
  });

  it("keeps the best-connected nodes when over the limit", () => {
    const chosen = selectLabels(
      [node("low", 1), node("high", 9), node("mid", 5), node("none", 0)],
      VIEW,
      2,
    );
    expect(chosen).toEqual(new Set(["high", "mid"]));
  });

  it("ranks pages before tags and sources however connected those are", () => {
    // A tag that has become a hub would otherwise take the top slot from the
    // pages the reader came to read.
    const chosen = selectLabels(
      [node("tag", 50, { secondary: true }), node("p1", 1), node("p2", 2)],
      VIEW,
      2,
    );
    expect(chosen).toEqual(new Set(["p1", "p2"]));
  });

  it("fills slots the pages leave over with tags and sources, by degree", () => {
    const chosen = selectLabels(
      [node("p", 1), node("t-low", 1, { secondary: true }), node("t-high", 7, { secondary: true })],
      VIEW,
      2,
    );
    expect(chosen).toEqual(new Set(["p", "t-high"]));
  });

  it("breaks degree ties by id, so the choice does not flicker between frames", () => {
    const a = selectLabels([node("b", 1), node("a", 1), node("c", 1)], VIEW, 2);
    const b = selectLabels([node("c", 1), node("b", 1), node("a", 1)], VIEW, 2);
    expect(a).toEqual(new Set(["a", "b"]));
    expect(b).toEqual(a);
  });

  it("never returns more than the limit", () => {
    const many = Array.from({ length: 1000 }, (_, i) =>
      node("n" + i, i % 7, { x: (i % 200) - 100 }),
    );
    expect(selectLabels(many, VIEW, 40)?.size).toBe(40);
  });
});

describe("restingLabelAlpha", () => {
  it("is 1 for a chosen label and 0 otherwise — no half-transparent middle", () => {
    expect(restingLabelAlpha(true, 0.4)).toBe(1);
    expect(restingLabelAlpha(false, 0.4)).toBe(0);
  });

  it("falls back to the zoom ramp when no limit is in force", () => {
    expect(restingLabelAlpha(undefined, 0.4)).toBe(0.4);
  });

  it("still loses to hover: a chosen non-neighbour goes to 0 while focusing", () => {
    expect(labelAlpha(false, false, true, restingLabelAlpha(true, 0))).toBe(0);
    expect(labelAlpha(false, true, true, restingLabelAlpha(false, 0))).toBe(1);
  });
});

describe("normalizeLabelLimit", () => {
  it("defaults to 40", () => {
    expect(DEFAULT_LABEL_LIMIT).toBe(40);
    expect(normalizeLabelLimit(undefined)).toBe(40);
    expect(normalizeLabelLimit("abc")).toBe(40);
    expect(normalizeLabelLimit(-1)).toBe(40);
  });

  it("keeps 0, which means no limit", () => {
    expect(normalizeLabelLimit(0)).toBe(0);
  });

  it("floors fractions and reads numeric strings", () => {
    expect(normalizeLabelLimit(12.7)).toBe(12);
    expect(normalizeLabelLimit("15")).toBe(15);
  });
});

describe("the inline script wires the label limit", () => {
  function fn(name: string): string {
    const start = INLINE.indexOf("function " + name + "(");
    expect(start, name).toBeGreaterThan(-1);
    return INLINE.slice(start, INLINE.indexOf("\n      }\n", start));
  }

  it("applies the limit to the global graph only", () => {
    // The local graph holds a neighbourhood and has no bar to change it from.
    expect(INLINE).toMatch(
      /var labelLimit = depth < 0 \? normalizeLabelLimit\(config\.labelLimit\) : 0;/,
    );
  });

  it("chooses labels inside renderLabels, the one writer", () => {
    expect(fn("renderLabels")).toContain("selectLabels(");
    expect(fn("renderLabels")).toContain("restingLabelAlpha(");
  });

  it("redoes the choice per tick while a limit is in force", () => {
    expect(INLINE).toMatch(
      /simulation\.on\("tick", function \(\) \{\s*if \(labelLimit > 0\) renderLabels\(\);/,
    );
  });

  it("changes the limit without rebuilding the graph", () => {
    // showGlobalGraph() re-seeds the simulation, which loses the layout.
    expect(INLINE).toContain("update({ labelLimit: v }, true);");
    expect(INLINE).toMatch(/relabelOnly \? labelLimitSetters\.get\(graphContainer\)/);
  });

  it("stores the limit only when it differs from the quartz.config.yaml value", () => {
    // Storing it on every filter change (or on Reset) would pin the YAML value
    // of the day in the browser and hide a later retune from the reader.
    expect(INLINE).toContain("if (nextLimit !== configuredLabelLimit(graphContainer)) {");
    expect(INLINE).toContain("filters.labelLimit = nextLimit;");
  });

  it("resets to the quartz.config.yaml value, not to a constant", () => {
    expect(INLINE).toContain("labelLimit: configuredLabelLimit(graphContainer),");
    expect(INLINE).toContain(
      'graphContainer.dataset["cfgDefault"] = graphContainer.dataset["cfg"]',
    );
  });
});

describe("label limit strings", () => {
  it("every locale carries them, with an ASCII 0 in the hint", () => {
    const dir = join(import.meta.dirname, "..", "i18n", "locales");
    const codes = readdirSync(dir)
      .filter((f) => f.endsWith(".ts"))
      .map((f) => f.replace(/\.ts$/, ""));
    expect(codes.length).toBeGreaterThan(1);
    for (const code of codes) {
      const controls = i18n(code).components.graph.controls as Record<string, string>;
      expect(controls.labelLimit, `${code}.labelLimit`).toBeTruthy();
      expect(controls.labelLimitHint, `${code}.labelLimitHint`).toContain("0");
    }
  });
});
