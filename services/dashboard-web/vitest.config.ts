import { join } from "node:path";

import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": join(import.meta.dirname, "src"),
            // The real package throws outside a server bundle; the tests run server modules directly.
            "server-only": join(import.meta.dirname, "src/test/server-only.ts"),
        },
    },
    test: {
        environment: "jsdom",
        setupFiles: ["./src/test/setup.ts"],
        css: false,
        // Playwright specs run against a live stack (`pnpm e2e`), not here.
        exclude: [...configDefaults.exclude, "e2e/**"],
    },
});
