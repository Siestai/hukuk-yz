import { join } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

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
    },
});
