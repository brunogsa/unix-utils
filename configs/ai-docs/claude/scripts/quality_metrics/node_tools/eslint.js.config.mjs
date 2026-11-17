// Measures unused variables in JavaScript files.
// It skips the repo's own ESLint config on purpose, so a repo
// that disables the rule cannot hide its unused code.
export default [
  {
    files: ["**/*.js", "**/*.jsx", "**/*.mjs", "**/*.cjs"],

    // The default parser reads JSX only when told to.
    languageOptions: { parserOptions: { ecmaFeatures: { jsx: true } } },
    rules: { "no-unused-vars": "error" },
  },
];
