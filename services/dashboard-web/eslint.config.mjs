import js from "@eslint/js";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";
import i18next from "eslint-plugin-i18next";
import { defineConfig, globalIgnores } from "eslint/config";

// Hard-coded colors and arbitrary Tailwind values belong in design tokens (frontend-ui skill).
const tokenOnlyMessage = "Use design tokens (packages/ui styles), not hard-coded values.";
const forbiddenStyleValues = [
    /#[0-9a-fA-F]{3,8}\b/.source,
    /rgba?\(/.source,
    /\w-\[[^\]]+\]/.source,
].map((pattern) => ({
    selector: `:matches(Literal[value=/${pattern}/], TemplateElement[value.raw=/${pattern}/])`,
    message: tokenOnlyMessage,
}));

// The UI talks to `app` over HTTP only (architecture.md): no database clients in the frontend.
const dbClients = ["prisma", "@prisma/client", "drizzle-orm", "pg", "postgres", "kysely"];

export default defineConfig([
    globalIgnores([".next/", "coverage/", "node_modules/", "src/lib/api/schema.d.ts"]),
    js.configs.recommended,
    ...nextVitals,
    ...nextTypescript,
    i18next.configs["flat/recommended"],
    {
        files: ["**/*.{ts,tsx}"],
        rules: {
            "i18next/no-literal-string": ["error", { mode: "jsx-text-only" }],
            "no-restricted-syntax": ["error", ...forbiddenStyleValues],
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
