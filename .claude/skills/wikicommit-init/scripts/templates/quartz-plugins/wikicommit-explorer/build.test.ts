import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

// Regression test for Issue #399 (ships the wikicommit-jsonld build.test.ts
// pattern from Issue #186/#379 to this plugin): this plugin directory ships
// standalone (no node_modules of its own once copied into a user's wiki
// repo), so a bare `import ... from "preact"` in dist/index.js cannot be
// resolved at Quartz build time. tsup's automatic JSX runtime must inline the
// vnode helpers instead. This plugin previously set `noExternal: [/.*/]`,
// which bundled everything indiscriminately and happened to avoid a bare
// import only because it has no value import besides JSX; a component added
// later that value-imports something in SINGLETON_EXTERNALS (e.g. `unified`)
// would silently get bundled too, diverging from Quartz core's own copy.
// Runs the real tsup build to catch that class of regression, which unit
// tests against the pre-JSX-transform source cannot see. This also exercises
// the inlineScriptPlugin path (wikicommit-explorer.inline.ts), confirming the
// noExternal narrowing doesn't interfere with its separate esbuild.build()
// call.
describe("built dist/index.js (Issue #399)", () => {
  it("does not bare-import preact and still emits the explorer's own markup", () => {
    const outDir = mkdtempSync(join(tmpdir(), "wikicommit-explorer-build-"))
    try {
      execFileSync("npx", ["tsup", "--config", "tsup.config.ts", "--out-dir", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      })
      const built = readFileSync(join(outDir, "index.js"), "utf-8")
      expect(built).not.toMatch(/from\s+["']preact(\/[^"']*)?["']/)
      expect(built).toContain("explorer-content")
    } finally {
      rmSync(outDir, { recursive: true, force: true })
    }
  }, 30000)
})
