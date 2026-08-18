import { defineConfig } from "tsup"
import { baseTsupOptions } from "../_shared/tsup.base"

export default defineConfig({
  ...baseTsupOptions,
  entry: {
    index: "src/index.tsx",
  },
  // Only what JSX compilation actually needs bundled — never [/.*/], which
  // silently defeats every entry in SINGLETON_EXTERNALS (see
  // quartz-plugins/_shared/tsup.base.ts and Issue #379).
  noExternal: ["preact", "preact/jsx-runtime"],
})
