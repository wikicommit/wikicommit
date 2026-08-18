import { defineConfig } from "tsup"
import type { Plugin } from "esbuild"
import path from "path"
import { baseTsupOptions } from "../_shared/tsup.base"

// Same inline-script-loader pattern as wikicommit-explorer/wikicommit-search
// (originally vendored from github:quartz-community/explorer's
// tsup.config.ts): bundles *.inline.ts as minified browser JS text (rather
// than a normal ESM module) so QuartzComponent.afterDOMLoaded can embed it
// verbatim as an inline <script> at build time.
const inlineScriptPlugin: Plugin = {
  name: "inline-script-loader",
  setup(parentBuild) {
    const absWorkingDir = parentBuild.initialOptions.absWorkingDir ?? process.cwd()

    parentBuild.onLoad({ filter: /\.scss$/ }, async (args) => {
      const sass = await import("sass")
      const result = sass.compile(args.path)
      return { contents: result.css, loader: "text" }
    })

    parentBuild.onLoad({ filter: /\.inline\.ts$/ }, async (args) => {
      const esbuild = await import("esbuild")
      const fs = await import("fs")
      let text = await fs.promises.readFile(args.path, "utf8")
      text = text.replace(/^export default /gm, "")
      text = text.replace(/^export /gm, "")

      const resolveDir = path.dirname(args.path)
      const sourcefile = path.relative(absWorkingDir, args.path)

      const result = await esbuild.build({
        stdin: { contents: text, loader: "ts", resolveDir, sourcefile },
        write: false,
        bundle: true,
        minify: true,
        platform: "browser",
        format: "esm",
        target: "es2020",
        sourcemap: false,
        external: ["http://*", "https://*"],
      })

      const js = result.outputFiles?.[0]?.text
      if (!js) throw new Error(`inline-script-loader: no JS output for ${args.path}`)

      return { contents: js, loader: "text" }
    })
  },
}

export default defineConfig({
  ...baseTsupOptions,
  entry: {
    index: "src/index.ts",
    "components/index": "src/components/index.ts",
  },
  // gray-matter (bundled below via noExternal) does a plain top-level
  // `require("fs")` (unused by this plugin's own code path — only its
  // unused matter.read() file helper touches fs — but esbuild bundles it
  // regardless). Because gray-matter is a CJS module getting interop-wrapped
  // for this ESM build, esbuild routes *every* require() call inside it
  // (including this one, even though "fs" is a Node builtin) through a
  // runtime shim that falls back to `typeof require !== "undefined"` — true
  // under Node's CJS loader, but plain ESM output has no such global, so
  // this threw `Dynamic require of "fs" is not supported` at actual import
  // time (verified against a real dist/index.js build, not just unit
  // tests). Marking "fs" external on its own does not change this — the
  // interop wrapping happens regardless of the require target's external
  // status. tsup's `shims: true` doesn't cover this either: it only injects
  // `require`/`__dirname` polyfills for identifiers esbuild sees used
  // directly in this plugin's own pre-bundle source, not inside a nested
  // CJS dependency's already-bundled body. The banner below defines a real
  // `require` binding via node:module's createRequire so that runtime
  // `typeof require !== "undefined"` check succeeds for real instead of
  // hitting the shim's throw branch.
  banner: {
    js: "import { createRequire as __wcPropsCreateRequire } from 'node:module'; const require = __wcPropsCreateRequire(import.meta.url);",
  },
  // Only what JSX compilation actually needs bundled, plus this plugin's own
  // frontmatter-parsing dependencies — never [/.*/], which silently defeats
  // every entry in SINGLETON_EXTERNALS (see quartz-plugins/_shared/tsup.base.ts
  // and Issue #379). This narrowing does not affect inlineScriptPlugin's
  // *.inline.ts handling above — that loader runs its own separate, isolated
  // esbuild.build() call (browser target, its own bundle/external options)
  // to produce the inline <script> text, entirely independent of this
  // defineConfig's own noExternal/external.
  //
  // gray-matter/remark-frontmatter/js-yaml/toml are listed in this package's
  // own package.json "dependencies" (tsup's default is to leave anything
  // there as a bare unbundled import, same as it would for @quartz-community/
  // types|utils), but unlike those two this plugin ships with no node_modules
  // of its own once copied into a user's wiki repo (same standalone-directory
  // constraint _shared/tsup.base.ts documents for preact) — none of these
  // four are Quartz-core singletons a bare import could resolve against at
  // build time, so they must be bundled here instead.
  noExternal: ["preact", "preact/jsx-runtime", "gray-matter", "remark-frontmatter", "js-yaml", "toml"],
  esbuildPlugins: [inlineScriptPlugin],
})
