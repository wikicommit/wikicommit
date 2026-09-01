import { describe, expect, it } from "vitest";

import { controlsSignature } from "./controlBar";

const LABELS = { lang: "Language", type: "Type", reset: "Reset" };

describe("controlsSignature", () => {
  it("is stable across calls with equal input", () => {
    const facets = { langs: ["en", "ja"], types: ["Person", "Place"] };
    expect(controlsSignature(facets, LABELS)).toBe(controlsSignature(facets, LABELS));
  });

  it("ignores label key order", () => {
    // The labels are re-parsed from data-labels on every render; a different
    // key order must not read as a structural change and rebuild the bar.
    const facets = { langs: ["en"], types: [] };
    expect(controlsSignature(facets, { lang: "Language", reset: "Reset" })).toBe(
      controlsSignature(facets, { reset: "Reset", lang: "Language" }),
    );
  });

  it("changes when a facet list changes", () => {
    const before = controlsSignature({ langs: ["en"], types: ["Person"] }, LABELS);
    expect(controlsSignature({ langs: ["en", "ja"], types: ["Person"] }, LABELS)).not.toBe(before);
    expect(controlsSignature({ langs: ["en"], types: ["Person", "Place"] }, LABELS)).not.toBe(
      before,
    );
  });

  it("changes when a label changes", () => {
    const facets = { langs: ["en"], types: ["Person"] };
    expect(controlsSignature(facets, { ...LABELS, reset: "リセット" })).not.toBe(
      controlsSignature(facets, LABELS),
    );
  });

  it("does not confuse a lang facet with a type facet of the same name", () => {
    expect(controlsSignature({ langs: ["Person"], types: [] }, LABELS)).not.toBe(
      controlsSignature({ langs: [], types: ["Person"] }, LABELS),
    );
  });
});
