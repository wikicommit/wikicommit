import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

// Issue #840: the Sources / Tags toggles could not be read as on or off. Three
// things stacked up — the bar had no surface of its own, the toggles were the
// engine's own checkboxes, and the only difference between the two states was
// the check glyph, at 0.8rem.
//
// Read as source text for the reason `legend.test.ts` already gives: vitest
// aliases the inline script to a stub (the real one is assembled by the esbuild
// loader at build time), and the test environment is `node` with no DOM, so
// neither the component nor `buildToggle()` can be exercised here. These
// assertions therefore hold the *decisions* in place rather than the rendering —
// the rendering is what the pilot's published site has to confirm.
//
// Line comments are stripped on the way in. `block()` below finds a rule's end
// by counting braces, and this file's comments routinely quote CSS — a future
// one that names a nested rule (`&:hover { ... }`) would otherwise close the
// block early and quietly turn these assertions into whatever the truncated
// text happens to say. `[^:]` keeps `https://` out of it.
const SCSS = readFileSync(
  join(import.meta.dirname, "..", "src", "components", "styles", "graph.scss"),
  "utf-8",
).replace(/(^|[^:])\/\/[^\n]*/g, "$1");
const INLINE = readFileSync(
  join(import.meta.dirname, "..", "src", "components", "scripts", "graph.inline.ts"),
  "utf-8",
);

/** The body of one SCSS block, by selector, up to its closing brace. */
function block(selector: string): string {
  const start = SCSS.indexOf(`${selector} {`);
  expect(start, `${selector} is not in graph.scss`).toBeGreaterThan(-1);
  let depth = 0;
  for (let i = SCSS.indexOf("{", start); i < SCSS.length; i++) {
    if (SCSS[i] === "{") depth++;
    else if (SCSS[i] === "}" && --depth === 0) return SCSS.slice(start, i + 1);
  }
  throw new Error(`${selector} has no closing brace`);
}

/** Only a rule's *own* declarations, with every nested rule removed.
 *
 * `block()` returns a rule and everything nested inside it, which is not what
 * "does the bar paint a surface?" means: `.global-graph-controls` contains
 * `.global-graph-controls__toggle` and `.global-graph-controls__reset`, and
 * both of those declare `background-color: var(--light)`, `border: 1px solid
 * var(--lightgray)`, a `border-radius` and a `padding`. Asserting against the
 * whole block therefore passed with the bar's own surface deleted — the four
 * declarations this file exists to hold in place were not being held by
 * anything.
 */
function ownDeclarations(selector: string): string {
  const body = block(selector);
  const inner = body.slice(body.indexOf("{") + 1, body.lastIndexOf("}"));
  let out = "";
  let depth = 0;
  for (const ch of inner) {
    if (ch === "{") {
      // Drop the nested rule's selector too, back to the end of the last
      // declaration, so `.global-graph-controls__toggle` is not left behind.
      if (depth === 0) out = out.slice(0, out.lastIndexOf(";") + 1);
      depth++;
      continue;
    }
    if (ch === "}") {
      depth--;
      continue;
    }
    if (depth === 0) out += ch;
  }
  return out;
}

describe("the control bar has a surface of its own", () => {
  // Without one the bar floats directly on the page the modal was opened from,
  // seen through `.global-graph-outer`'s backdrop blur — a different background
  // every time, which is most of why the controls did not read as controls.
  const bar = ownDeclarations(".global-graph-controls");

  it("paints a background, a border and a radius", () => {
    expect(bar).toMatch(/background-color:\s*var\(--light\)/);
    expect(bar).toMatch(/border:\s*1px solid var\(--lightgray\)/);
    expect(bar).toMatch(/border-radius:/);
  });

  it("uses the same three declarations as the graph panel", () => {
    // So the bar and the graph read as two panels of one thing rather than a
    // panel with some text floating above it.
    const panel = ownDeclarations(".global-graph-container");
    for (const decl of [
      /background-color:\s*var\(--light\)/,
      /border:\s*1px solid var\(--lightgray\)/,
      /border-radius:\s*5px/,
    ]) {
      expect(panel).toMatch(decl);
      expect(bar).toMatch(decl);
    }
  });

  it("keeps padding inside the border", () => {
    // The surface is only legible if the controls are not flush against it.
    expect(bar).toMatch(/padding:\s*[^;]+;/);
  });
});

describe("the Sources / Tags toggles read as on or off", () => {
  it("are native buttons rather than checkboxes", () => {
    // A native <button> keeps Tab, Space, Enter and the focus ring with no
    // handler of our own — the things the checkbox gave for free and an element
    // merely styled as a button would have to re-implement.
    expect(INLINE).toContain('button.type = "button"');
    expect(INLINE).not.toContain('input.type = "checkbox"');
  });

  it("carry their state in aria-pressed", () => {
    expect(INLINE).toMatch(/setAttribute\(\s*"aria-pressed"/);
  });

  it("differ between states by a fill, not a glyph", () => {
    // The whole point: at 0.8rem an area of colour is readable where a check
    // mark is not.
    const toggle = block(".global-graph-controls__toggle");
    expect(toggle).toMatch(/&\[aria-pressed="true"\]/);
    const on = toggle.slice(toggle.indexOf('&[aria-pressed="true"]'));
    expect(on).toMatch(/background-color:\s*var\(--secondary\)/);
    expect(on).toMatch(/color:\s*var\(--light\)/);
  });

  it("share the visual vocabulary of the Reset button", () => {
    // Both are controls in the same bar; if only one looked pressable, the
    // other read as a caption — which is what happened.
    const toggle = block(".global-graph-controls__toggle");
    const reset = block(".global-graph-controls__reset");
    for (const decl of [
      /cursor:\s*pointer/,
      /border-radius:\s*4px/,
      /padding:\s*0\.2rem 0\.6rem/,
    ]) {
      expect(toggle).toMatch(decl);
      expect(reset).toMatch(decl);
    }
  });

  it("stay filled while hovered when on, without swapping to a theme-invariant colour", () => {
    // Reusing the off-state hover would make pointing at an enabled toggle look
    // like turning it off. --tertiary was the obvious fill to swap to and is
    // wrong: it is the same value in both themes while the text colour flips,
    // so it cannot be legible in both (2.53:1 against --light in light mode).
    const toggle = block(".global-graph-controls__toggle");
    const on = toggle.slice(toggle.indexOf('&[aria-pressed="true"]'));
    expect(on).toMatch(/&:hover\s*\{[^}]*filter:\s*brightness/);
    expect(on).not.toMatch(/&:hover\s*\{[^}]*var\(--tertiary\)/);
  });

  it("does not fill with a variable that stays the same in both themes", () => {
    // --secondary and --light both flip between themes, which is the only
    // reason one pair of variables reads in both; the test above holds that
    // pair. This one holds the other half of the same claim, which nothing
    // else does: a fill that is theme-invariant (--tertiary, --gray) cannot be
    // legible against a foreground that flips, whichever way round it is read.
    const toggle = block(".global-graph-controls__toggle");
    const on = toggle.slice(toggle.indexOf('&[aria-pressed="true"]'));
    expect(on).not.toMatch(/background-color:\s*var\(--(tertiary|gray)\)/);
  });

  it("keep the {field, sync} contract", () => {
    // Issue #651 updates the bar's values in place rather than rebuilding it,
    // and reaches the toggles through this shape. Changing what a toggle *is*
    // must not change what it returns.
    const fn = INLINE.slice(INLINE.indexOf("function buildToggle("));
    const body = fn.slice(0, fn.indexOf("\n    function ", 1));
    expect(body).toMatch(/return\s*\{[\s\S]*field:/);
    expect(body).toMatch(/sync:\s*function/);
  });
});

describe("the shared field styling names the types it applies to", () => {
  it("no longer matches every input", () => {
    // As a bare `select, input` this also matched the toggles' checkboxes,
    // where background-color and border do nothing without `appearance: none` —
    // so whether those declarations applied was engine-dependent, and reading
    // the block gave no way to tell.
    const bar = block(".global-graph-controls");
    expect(bar).toContain('input[type="number"]');
    expect(bar).not.toMatch(/^\s*input\s*\{/m);
  });
});
