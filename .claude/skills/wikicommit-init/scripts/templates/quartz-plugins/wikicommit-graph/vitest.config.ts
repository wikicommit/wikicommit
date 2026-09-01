import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    environment: "node",
    // Upstream restricts this to test/**; the fork also unit-tests
    // src/util/nodeFilter.ts, which sits beside the code it describes (the
    // same placement wikicommit-explorer uses for src/util/foldLang.test.ts).
    include: ["test/**/*.test.ts", "src/**/*.test.ts"],
    reporters: ["default"],
    alias: {
      "./styles/graph.scss": path.resolve(__dirname, "test/__mocks__/styleMock.ts"),
      "./scripts/graph.inline.ts": path.resolve(__dirname, "test/__mocks__/scriptMock.ts"),
    },
  },
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "preact",
  },
});
