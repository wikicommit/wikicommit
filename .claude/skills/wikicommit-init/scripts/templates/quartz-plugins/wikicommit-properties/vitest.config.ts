import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    environment: "node",
    // The real wikicommitProperties.inline.ts runs
    // `document.addEventListener(...)` at import time, which throws outside
    // a browser. Same pattern as wikicommit-explorer/wikicommit-search (see
    // their own vitest.config.ts) — the underlying logic that matters for
    // this plugin (getVisibleProperties() flattening) is unit-tested
    // directly in src/transformer.test.ts instead.
    alias: {
      "./scripts/wikicommitProperties.inline.ts": path.resolve(
        __dirname,
        "test/__mocks__/scriptMock.ts",
      ),
    },
  },
})
