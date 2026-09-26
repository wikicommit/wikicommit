import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { labelAlpha, zoomLabelAlpha } from "./labelOpacity";

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
