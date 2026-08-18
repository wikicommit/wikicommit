import { execFileSync } from "node:child_process"
import { mkdtempSync, readFileSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

// Regression test for Issue #379 (see wikicommit-sources/wikicommit-jsonld's
// own build.test.ts): this plugin directory ships standalone (no
// node_modules of its own once copied into a user's wiki repo), so a bare
// `import ... from "preact"` in dist/components/index.js cannot be resolved
// at Quartz build time — tsup's automatic JSX runtime must inline the
// vnode-creation helpers instead. Runs the real tsup build to catch that
// class of regression, which unit tests against the pre-JSX-transform source
// cannot see.
describe("built dist/components/index.js (Issue #379)", () => {
  it("does not bare-import preact and still emits the properties component's own markup", () => {
    const outDir = mkdtempSync(join(tmpdir(), "wikicommit-properties-build-"))
    try {
      execFileSync("npx", ["tsup", "--config", "tsup.config.ts", "--out-dir", outDir], {
        cwd: process.cwd(),
        stdio: "pipe",
      })
      const built = readFileSync(join(outDir, "components/index.js"), "utf-8")
      expect(built).not.toMatch(/from\s+["']preact(\/[^"']*)?["']/)
      expect(built).toContain("wikicommit-properties-table")

      const transformerBuilt = readFileSync(join(outDir, "index.js"), "utf-8")
      expect(transformerBuilt).toContain("WikiCommitProperties")
    } finally {
      rmSync(outDir, { recursive: true, force: true })
    }
  }, 30000)
})
