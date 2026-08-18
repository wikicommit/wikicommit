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
// the inlineScriptPlugin path (search.inline.ts), confirming the noExternal
// narrowing doesn't interfere with its separate esbuild.build() call.
//
// Lives under test/ (unlike the other plugins' build.test.ts, which sit at
// the plugin root) because this plugin's vitest.config.ts restricts
// discovery to `test/**/*.test.ts` rather than vitest's default glob — a
// root-level file here would silently never run. `execFileSync`'s
// `cwd: process.cwd()` still resolves `tsup.config.ts` correctly regardless
// of this file's own location, since `npm test`/`vitest run` set
// process.cwd() to the plugin root, not to this file's directory.
describe("built dist/index.js (Issue #399)", () => {
  it("does not bare-import preact and still emits the search box's own markup", () => {
    const outDir = mkdtempSync(join(tmpdir(), "wikicommit-search-build-"))
    try {
      execFileSync("npx", ["tsup", "--config", "tsup.config.ts", "--out-dir", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      })
      const built = readFileSync(join(outDir, "index.js"), "utf-8")
      expect(built).not.toMatch(/from\s+["']preact(\/[^"']*)?["']/)
      expect(built).toContain("search-container")
    } finally {
      rmSync(outDir, { recursive: true, force: true })
    }
  }, 30000)
})
