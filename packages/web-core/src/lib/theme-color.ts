/**
 * The browser chrome color of a phone (`<meta name="theme-color">`): the `--surface` token of
 * packages/ui/src/styles.css, the color of the mobile top bar. A meta tag cannot read a CSS
 * variable, so the value is repeated here once; theme-color.test.ts fails if the two drift.
 */
// eslint-disable-next-line no-restricted-syntax -- the one place a color is written outside the tokens
export const THEME_COLOR = "#ffffff";
