import base from "../dashboard-web/eslint.config.mjs";

// The rules (design tokens, no literal texts, no database clients) are the dashboard's; only the
// Next plugin is pointed at this app.
const config = [...base, { settings: { next: { rootDir: import.meta.dirname } } }];

export default config;
