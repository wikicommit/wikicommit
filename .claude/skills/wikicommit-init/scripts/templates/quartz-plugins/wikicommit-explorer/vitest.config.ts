import { defineConfig } from "vitest/config"
import path from "path"

export default defineConfig({
  test: {
    environment: "node",
    // The real wikicommit-explorer.inline.ts runs `document.addEventListener(...)`
    // at import time, which throws outside a browser. Upstream
    // github:quartz-community/explorer aliases the same import to a mock for
    // the same reason (see its test/__mocks__/scriptMock.ts) — the fold logic
    // itself is unit-tested directly in src/util/foldLang.test.ts instead.
    alias: {
      "./scripts/wikicommit-explorer.inline.ts": path.resolve(
        __dirname,
        "test/__mocks__/scriptMock.ts",
      ),
    },
  },
})
