import { defineConfig } from "tsup"
import type { Plugin } from "esbuild"
import path from "path"
import { baseTsupOptions } from "../_shared/tsup.base"

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
  // Only what JSX compilation actually needs bundled — never [/.*/], which
  // silently defeats every entry in SINGLETON_EXTERNALS (Issue #399: this
  // plugin previously used [/.*/], the same latent bug Issue #379 fixed for
  // wikicommit-banner/wikicommit-jsonld/wikicommit-sources). This narrowing
  // does not affect inlineScriptPlugin's *.inline.ts handling below — that
  // loader runs its own separate, isolated esbuild.build() call (browser
  // target, its own `bundle`/`external` options) to produce the inline
  // <script> text, entirely independent of this defineConfig's own
  // noExternal/external.
  // See quartz-plugins/_shared/tsup.base.ts for the JSX-only constraint this
  // narrowing depends on.
  noExternal: ["preact", "preact/jsx-runtime"],
  esbuildPlugins: [inlineScriptPlugin],
})
