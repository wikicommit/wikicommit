import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier";

export default tseslint.config(
  {
    // src/components/scripts/*.inline.ts is plain browser JS (loaded as raw
    // text by the tsup esbuild plugin, not compiled through this package's
    // own tsconfig — same reasoning as wikicommit-explorer's ignore for the
    // same category of file, and the ignorePatterns entry this replaces).
    ignores: ["dist/**", "src/components/scripts/*.inline.ts"],
  },
  ...tseslint.configs.recommended,
  eslintConfigPrettier,
  {
    rules: {
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
    },
  },
  {
    // types/globals.d.ts intentionally uses a triple-slash reference (not an
    // import) to pull in @quartz-community/types/globals.d.ts's ambient
    // `declare global` augmentations — replacing it with an `import`
    // statement would turn this file into a module, making those `declare
    // module` blocks locally scoped instead of global (verified: doing so
    // breaks `tsc --noEmit` with "Cannot find module '*.scss'" errors
    // elsewhere in this package). This mirrors the legacy .eslintrc.json's
    // now-removed override for the same rule on the same file.
    files: ["types/**/*.d.ts"],
    rules: {
      "@typescript-eslint/triple-slash-reference": "off",
    },
  },
);
