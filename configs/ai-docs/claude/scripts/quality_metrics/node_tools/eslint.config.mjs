// Measures unused variables in TypeScript files.
// It skips the repo's own ESLint config on purpose, so a repo
// that disables the rule cannot hide its unused code.
import tseslint from "typescript-eslint";

export default [
  {
    files: ["**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"],
    languageOptions: {
      parser: tseslint.parser,

      // The parser reads JSX only in .tsx files.
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "@typescript-eslint": tseslint.plugin },
    rules: { "@typescript-eslint/no-unused-vars": "error" },
  },
];
