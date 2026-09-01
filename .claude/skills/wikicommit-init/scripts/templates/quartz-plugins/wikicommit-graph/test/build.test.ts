import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Every component-bearing plugin here ships this test (Issue #186/#379/#399).
// A plugin directory ships standalone — once wikicommit-init copies it into a
// user's wiki repo it has no node_modules of its own — so a bare
// `import ... from "preact"` in dist/index.js cannot be resolved at Quartz
// build time; tsup's automatic JSX runtime has to inline the vnode helpers
// instead. Upstream github:quartz-community/graph sets `noExternal: [/.*/]`,
// which bundles everything indiscriminately and defeats SINGLETON_EXTERNALS;
// the fork narrows that to preact + preact/jsx-runtime, and this test is what
// keeps the narrowing honest. Only the real tsup build can catch this class of
// regression — unit tests run against the pre-JSX-transform source.
//
// It also exercises the inlineScriptPlugin path (graph.inline.ts), which
// imports src/util/nodeFilter.ts and src/util/controlBar.ts: that loader runs
// its own isolated esbuild.build(), so a failure to bundle either import would
// surface here rather than in typecheck. Every module the inline script pulls
// in needs an assertion of its own — an unresolved specifier is not a build
// error, it is a page that loads a script the browser then refuses to run.
describe("built dist/index.js", () => {
  it("does not bare-import preact and inlines the graph script with the fork's filter code", () => {
    const outDir = mkdtempSync(join(tmpdir(), "wikicommit-graph-build-"));
    try {
      execFileSync("npx", ["tsup", "--config", "tsup.config.ts", "--out-dir", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      });
      const built = readFileSync(join(outDir, "index.js"), "utf-8");
      expect(built).not.toMatch(/from\s+["']preact(\/[^"']*)?["']/);
      // The component's own markup, including the fork's control-bar slot.
      expect(built).toContain("global-graph-controls");
      // nodeFilter.ts reached the inlined script rather than being left as an
      // unresolved import.
      expect(built).not.toMatch(/from\s*["'][^"']*nodeFilter["']/);
      expect(built).toContain("wikicommit-graph-filters");
      // controlBar.ts likewise (Issue #651): the control bar is reused across
      // renders only when its signature is computed, so an unbundled import
      // here takes the whole graph down.
      expect(built).not.toMatch(/from\s*["'][^"']*controlBar["']/);
      expect(built).toContain("childElementCount");
    } finally {
      rmSync(outDir, { recursive: true, force: true });
    }
  }, 60000);
});
