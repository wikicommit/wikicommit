import tseslint from "typescript-eslint"

export default tseslint.config(
  {
    // src/components/scripts/*.inline.ts is plain browser JS (loaded as raw
    // text by the tsup esbuild plugin, not compiled through this package's
    // own tsconfig — see the matching @ts-nocheck pragma in the file itself
    // and the ignorePatterns in upstream github:quartz-community/explorer's
    // .eslintrc.json).
    ignores: ["dist/**", "src/components/scripts/*.inline.ts"],
  },
  ...tseslint.configs.recommended,
)
