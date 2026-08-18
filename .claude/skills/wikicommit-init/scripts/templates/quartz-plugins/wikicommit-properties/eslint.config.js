import tseslint from "typescript-eslint"

export default tseslint.config(
  {
    ignores: ["dist/**"],
  },
  ...tseslint.configs.recommended,
  {
    // types/globals.d.ts intentionally uses a triple-slash reference (not an
    // import) to pull in @quartz-community/types/globals.d.ts's ambient
    // `declare global` augmentations — replacing it with an `import`
    // statement would turn this file into a module, making those `declare
    // module` blocks locally scoped instead of global. Same override as
    // wikicommit-search's eslint.config.js for the same reason.
    files: ["types/**/*.d.ts"],
    rules: {
      "@typescript-eslint/triple-slash-reference": "off",
    },
  },
)
