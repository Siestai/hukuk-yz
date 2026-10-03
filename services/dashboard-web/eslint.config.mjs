import js from "@eslint/js";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import i18next from "eslint-plugin-i18next";
import { defineConfig, globalIgnores } from "eslint/config";

// Hard-coded colors, arbitrary Tailwind values and inline styles belong in design tokens
// (frontend-ui skill). `esquery` regexes cannot contain "/", hence \x2f.
const tokenOnlyMessage = "Use design tokens (packages/ui styles), not hard-coded values.";
const hex = /(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b/.source;
// Anchors and ids look like hex colors ("#decade"); they are not colors.
const anchorAttributes = /^(?:href|id|htmlFor|name|aria-controls|aria-labelledby|aria-describedby)$/
    .source;
const stringPatterns = [
    // The whole string is a hex color.
    { pattern: `^\\s*#${hex}\\s*$`, literalOnly: true, notIn: anchorAttributes },
    // A hex color in a style value, bracket, function argument or border/shadow shorthand.
    {
        pattern: `(?:[\\w-]+\\s*:[^;]*|\\[[^\\]]*|\\([^)]*|(?:solid|dashed|dotted|double|inset|outset|groove|ridge|\\d(?:px|r?em)?)\\s+)#${hex}`,
    },
    // Color functions other than the token CSS variables.
    { pattern: /\b(?:rgba?|hsla?|oklch|oklab|hwb|lab|lch|color-mix)\(/.source },
    // Arbitrary Tailwind values (`p-[13px]`, `bg-primary/[.5]`). Variants end in ":" (`has-[...]:`,
    // `data-[x=y]:`, `[&>svg]:`, `group-has-[...]/name:`), `[var(--token)]` is allowed.
    {
        pattern:
            "[-\\x2f]\\[(?!(?:[a-z]+:)?var\\(--[\\w-]+\\)\\])(?:[^\\[\\]]|\\[[^\\]]*\\])+\\](?!(?:\\x2f[\\w-]+)?:)",
    },
].map(({ pattern, literalOnly, notIn }) => {
    const literal = notIn
        ? `:not(JSXAttribute[name.name=/${notIn}/]) > Literal[value=/${pattern}/]`
        : `Literal[value=/${pattern}/]`;
    return {
        selector: literalOnly
            ? literal
            : `:matches(${literal}, TemplateElement[value.raw=/${pattern}/])`,
        message: tokenOnlyMessage,
    };
});

// User-facing text must come from messages. i18next/no-literal-string (jsx-text-only) covers JSX
// text; these selectors cover text attributes and string/template expressions as JSX children.
const letter = "[A-Za-zÇĞİÖŞÜçğıöşü]";
const textAttributes = "placeholder|aria-label|aria-description|title|alt|label";
const textSlots = (container) =>
    ["", "ConditionalExpression > ", "LogicalExpression > "].flatMap((via) => [
        `${container} > ${via}Literal[value=/${letter}/]`,
        `${container} > ${via}TemplateLiteral:has(> TemplateElement[value.raw=/${letter}/])`,
    ]);
const literalTextMessage = "User-facing text must come from a message key (next-intl).";
const literalTextSelectors = [
    `JSXAttribute[name.name=/^(?:${textAttributes})$/] > Literal[value=/${letter}/]`,
    ...textSlots(`JSXAttribute[name.name=/^(?:${textAttributes})$/] > JSXExpressionContainer`),
    ...textSlots(":matches(JSXElement, JSXFragment) > JSXExpressionContainer"),
].map((selector) => ({ selector, message: literalTextMessage }));

const inlineStyle = {
    selector: "JSXAttribute[name.name='style']",
    message:
        "No inline styles: use token classes. Opt out with an eslint-disable comment that states the reason.",
};

// The UI talks to `app` over HTTP only (architecture.md): no database clients in the frontend.
const dbClients = ["prisma", "@prisma/client", "drizzle-orm", "pg", "postgres", "kysely"];

export default defineConfig([
    globalIgnores([".next/", "coverage/", "node_modules/", "src/lib/api/schema.d.ts"]),
    js.configs.recommended,
    ...nextVitals,
    ...nextTypescript,
    i18next.configs["flat/recommended"],
    // packages/ui is linted with this config too; point the Next plugin at the app.
    { settings: { next: { rootDir: import.meta.dirname } } },
    {
        files: ["**/*.{ts,tsx}"],
        rules: {
            "i18next/no-literal-string": ["error", { mode: "jsx-text-only" }],
            "no-restricted-syntax": [
                "error",
                ...stringPatterns,
                ...literalTextSelectors,
                inlineStyle,
            ],
            "no-restricted-imports": [
                "error",
                {
                    patterns: dbClients.map((name) => ({
                        group: [name, `${name}/*`],
                        message: "No database clients in the frontend; use the app API.",
                    })),
                },
            ],
        },
    },
    {
        files: ["**/*.test.{ts,tsx}", "**/test/**"],
        rules: { "i18next/no-literal-string": "off", "no-restricted-syntax": "off" },
    },
]);
