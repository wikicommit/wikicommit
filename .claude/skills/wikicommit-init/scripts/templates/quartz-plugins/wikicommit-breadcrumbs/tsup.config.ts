import { defineConfig } from "tsup"
import { baseTsupOptions } from "../_shared/tsup.base"

export default defineConfig({
  ...baseTsupOptions,
  entry: {
    index: "src/index.ts",
    "components/index": "src/components/index.ts",
  },
  // Only what JSX compilation actually needs bundled — never [/.*/], which
  // silently defeats every entry in SINGLETON_EXTERNALS (Issue #399: this
  // plugin previously used [/.*/], the same latent bug Issue #379 fixed for
  // wikicommit-banner/wikicommit-jsonld/wikicommit-sources).
  // See quartz-plugins/_shared/tsup.base.ts for the JSX-only constraint this
  // narrowing depends on.
  noExternal: ["preact", "preact/jsx-runtime"],
  esbuildPlugins: [
    {
      name: "text-loader",
      setup(build) {
        build.onLoad({ filter: /\.scss$/ }, async (args) => {
          const sass = await import("sass")
          const result = sass.compile(args.path)
          return { contents: result.css, loader: "text" }
        })
      },
    },
  ],
})
