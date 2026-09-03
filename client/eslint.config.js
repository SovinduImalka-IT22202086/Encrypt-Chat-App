// ESLint flat configuration for the Encrypted Chat Application client.
//
// Tooling note: the Vite template scaffolds `oxlint` by default. It was
// removed in favour of ESLint + typescript-eslint because Phase 1 specifies
// that stack, and running two linters would be overlapping tooling.

import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import globals from 'globals'

export default tseslint.config(
  {
    ignores: ['dist/**', 'coverage/**', 'node_modules/**'],
  },
  js.configs.recommended,
  // Type-aware linting: required for the rules below that need type info.
  ...tseslint.configs.recommendedTypeChecked,
  // v7 exposes flat-config variants under `.configs.flat`; the top-level
  // entries are still legacy (eslintrc) shaped and fail under ESLint 10.
  reactHooks.configs.flat['recommended-latest'],
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // --- Security-relevant rules ---------------------------------------
      // CLIENT-001 (no raw HTML rendering of untrusted content) is not
      // enforceable by these plugins alone; a `react/no-danger` rule should
      // be added with eslint-plugin-react in Phase 8, when message rendering
      // actually exists. Recorded here so it is not forgotten.
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      '@typescript-eslint/no-implied-eval': 'error',

      // Unsafe `any` flow is the usual way type guarantees get lost around
      // crypto and network boundaries later; keep these as warnings for now
      // so the scaffold is clean without hiding the signal.
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },
  // Config and test files are not part of the app's type-checked project.
  {
    files: ['*.config.{js,ts}', 'src/test/**/*.{ts,tsx}'],
    ...tseslint.configs.disableTypeChecked,
  },
)
