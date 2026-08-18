import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

// Regression test for Issue #186: this plugin directory ships standalone
// (no node_modules of its own once copied into a user's wiki repo), so a
// bare `import ... from "preact"` in dist/index.js cannot be resolved at
// Quartz build time. tsup's automatic JSX runtime must inline the vnode
// helpers instead. Runs the real tsup build to catch a regression that
// unit tests against the pre-JSX-transform source could miss.
describe("built dist/index.js (Issue #186)", () => {
  it("does not bare-import preact and still emits JSON-LD script markup", () => {
    const outDir = mkdtempSync(join(tmpdir(), "wikicommit-jsonld-build-"))
    try {
      execFileSync("npx", ["tsup", "--config", "tsup.config.ts", "--out-dir", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      })
      const built = readFileSync(join(outDir, "index.js"), "utf-8")
      expect(built).not.toMatch(/from\s+["']preact(\/[^"']*)?["']/)
      expect(built).toContain("application/ld+json")
    } finally {
      rmSync(outDir, { recursive: true, force: true })
    }
  }, 30000)
})
