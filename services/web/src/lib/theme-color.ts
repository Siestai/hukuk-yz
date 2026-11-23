/**
 * The browser chrome color of a phone (`<meta name="theme-color">`): the `--bg` token of the chat
 * theme in src/app/globals.css, the color of the mobile top bar. A meta tag cannot read a CSS
 * variable, so the value is repeated here once; theme-color.test.ts fails if the two drift.
 */
// eslint-disable-next-line no-restricted-syntax -- the one place a color is written outside the tokens
export const THEME_COLOR = "#f6f1e6";
