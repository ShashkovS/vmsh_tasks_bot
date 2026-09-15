export default {
  extends: ['stylelint-config-standard'],
  ignoreFiles: [
    '**/dist/**',
    '**/dev-dist/**',
    '**/node_modules/**',
    'storybook-static/**',
    'playwright-report/**',
  ],
  rules: {
    // Preserve the project's compact OKLCH notation and existing token layout.
    'alpha-value-notation': null,
    'at-rule-no-unknown': [
      true,
      {
        ignoreAtRules: ['apply', 'custom-variant', 'layer', 'source', 'theme'],
      },
    ],
    'comment-empty-line-before': null,
    'custom-property-pattern': null,
    'custom-property-empty-line-before': null,
    'declaration-block-no-redundant-longhand-properties': null,
    'declaration-empty-line-before': null,
    'hue-degree-notation': null,
    'import-notation': null,
    'lightness-notation': null,
    'media-feature-range-notation': null,
    'no-descending-specificity': null,
    'no-duplicate-selectors': null,
    'selector-class-pattern': null,
    'value-keyword-case': null,
  },
}
