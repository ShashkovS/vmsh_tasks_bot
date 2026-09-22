import eslint from '@eslint/js'
import globals from 'globals'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import pluginLingui from 'eslint-plugin-lingui'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

import i18nScopes from './i18n-scopes.json' with { type: 'json' }

export default tseslint.config(
  {
    ignores: [
      '**/dist/**',
      '**/dev-dist/**',
      '**/routeTree.gen.ts',
      'storybook-static/**',
      'playwright-report/**',
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked.map((config) => ({
    ...config,
    files: ['**/*.{ts,tsx}'],
  })),
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2024,
      globals: { ...globals.browser, ...globals.node },
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'jsx-a11y': jsxA11y,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-misused-promises': ['error', { checksVoidReturn: false }],
    },
  },
  {
    // Lingui macro hygiene everywhere; see docs/i18n.md.
    files: ['**/*.{ts,tsx}'],
    plugins: { lingui: pluginLingui },
    rules: {
      'lingui/t-call-in-function': 'error',
      'lingui/no-single-tag-to-translate': 'error',
      'lingui/no-single-variables-to-translate': 'error',
      'lingui/no-trans-inside-trans': 'error',
      // Positional placeholders ({0}) are fine: PO comments name their source.
      'lingui/no-expression-in-message': 'off',
    },
  },
  {
    // Translated scopes (i18n-scopes.json) must not contain unwrapped Russian
    // copy. Strings without Cyrillic are technical and stay allowed.
    files: i18nScopes.frontend,
    ignores: ['**/*.test.{ts,tsx}', '**/*.stories.{ts,tsx}'],
    rules: {
      'lingui/no-unlocalized-strings': ['error', { ignore: ['^[^А-Яа-яЁё]*$'] }],
    },
  },
  {
    files: ['**/*.stories.{ts,tsx}', '**/*.test.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
    },
  },
  {
    // Shared packages are libraries, not app entry points — fast-refresh
    // component-only export granularity does not apply.
    files: ['packages/*/src/**/*.{ts,tsx}'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    // Design-system exploration exports component registries by design; fast
    // refresh granularity is irrelevant for Storybook-only material.
    files: ['dev/design-system/**/*.{ts,tsx}'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
  {
    // Node scripts that also contain browser code evaluated inside Playwright.
    files: ['**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2024,
      globals: { ...globals.browser, ...globals.node },
    },
  },
)
