import type { Options } from "tsup"

// Shared by every quartz-plugins/*/tsup.config.ts (Issue #379). These packages
// build into ESM entry points that Quartz's own bundler loads alongside its
// own copies of preact/vfile/unified/@jackyzha0/quartz. If a plugin's build
// bundles its own copy of one of those instead of importing it as an
// external module, the two copies diverge into separate module identities
// (e.g. preact's Context objects stop comparing equal across plugin and
// core), breaking anything that relies on singleton behavior.
// `external: SINGLETON_EXTERNALS` guards against this — but only for
// packages not also matched by a plugin's own `noExternal`, since tsup/esbuild
// lets `noExternal` win over `external` on a conflict (verified against tsup
// v8.5.1). Each plugin still sets its own `noExternal` (only what it actually
// needs bundled, e.g. `preact`/`preact/jsx-runtime` for JSX support — never
// `[/.*/]`, which silently defeats every entry in SINGLETON_EXTERNALS) and its
// own `entry`/`esbuildPlugins` (SCSS/inline-script loaders differ per
// plugin); this file only factors out what previously drifted out of sync by
// copy-paste — SINGLETON_EXTERNALS itself, plus the defineConfig options that
// never vary per plugin.
//
// This directory (quartz-plugins/_shared/) is not an npm package — it has no
// package.json and ships no dist/. It exists purely so each plugin's
// tsup.config.ts can `import` it by relative path; wikicommit-init copies
// quartz-plugins/ into the user's repo as one tree (init.py), so the sibling
// relationship this relies on always holds after that copy.
//
// Each plugin's own tsconfig.json now excludes its tsup.config.ts (and never
// included this file to begin with): with `rootDir: "."` set per plugin
// (needed so `dist/` mirrors `src/` 1:1), a program that includes
// tsup.config.ts would also have to include this file — one directory above
// rootDir — which `tsc` rejects (TS6059, "File is not under 'rootDir'").
// This has no effect on the actual build: tsup loads tsup.config.ts through
// its own esbuild-based bundling step, not through tsc/tsconfig.build.json,
// so it was never type-checked as part of `dts: true`'s output either —
// `tsconfig.build.json`'s `include: ["src", "types"]` already omitted it.
// `npm run typecheck` (`tsc --noEmit` against tsconfig.json) is the only
// place this changes anything, and it only stops checking the config file
// itself, not any file under src/.
//
// Constraint this build model depends on: components in these plugins may
// only produce vnodes through JSX syntax (compiled via the automatic
// jsx-runtime import below), never by calling preact's `h()`/`createElement`
// or `render()` directly. `noExternal` only ever lists `preact` +
// `preact/jsx-runtime` (see each plugin's own tsup.config.ts) — any other
// preact entry point used directly would either fail to resolve at Quartz
// build time (this plugin ships with no node_modules of its own once copied
// into a user's wiki repo) or get silently bundled as a second preact copy if
// someone "fixes" that by broadening noExternal again. Each plugin with a
// components/ entry point ships a build.test.ts that runs the real tsup build
// and asserts dist/index.js has no bare `import ... from "preact"` (Issue
// #186/#379) — add one for any new component-bearing plugin.
export const SINGLETON_EXTERNALS = [
  "preact",
  "preact/hooks",
  "preact/jsx-runtime",
  "preact/compat",
  "@jackyzha0/quartz",
  "@jackyzha0/quartz/*",
  "vfile",
  "vfile/*",
  "unified",
]

export const baseTsupOptions: Options = {
  format: ["esm"],
  dts: true,
  tsconfig: "tsconfig.build.json",
  sourcemap: true,
  clean: true,
  treeshake: true,
  target: "es2022",
  splitting: false,
  external: SINGLETON_EXTERNALS,
  outDir: "dist",
  platform: "node",
  esbuildOptions(options) {
    options.jsx = "automatic"
    options.jsxImportSource = "preact"
  },
}
