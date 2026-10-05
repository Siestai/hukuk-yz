import { join } from "node:path";

import { defineConfig, devices } from "@playwright/test";

// Runs against a live stack (`make dev` + `make demo-data`, see e2e/README.md); CI has none.
// Credentials come from the environment and are never committed.
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";
// The session file holds a login cookie: it stays under the gitignored .output/.
export const STORAGE_STATE = join(import.meta.dirname, ".output/state.json");

const browser = {
    ...devices["Desktop Chrome"],
    // E2E_CHANNEL=chromium: the full Chromium build, whose viewer renders the PDF tab; the default
    // headless shell has no PDF viewer.
    channel: process.env.E2E_CHANNEL || undefined,
    storageState: STORAGE_STATE,
};

// A phone: Chromium with touch and mobile emulation, so `pointer: coarse` matches. WebKit is not
// installed on the server; Safari is checked by hand.
const phone = {
    ...devices["Pixel 7"],
    channel: process.env.E2E_CHANNEL || undefined,
    storageState: STORAGE_STATE,
};

export default defineConfig({
    testDir: ".",
    outputDir: ".output/results",
    globalSetup: "./global-setup.ts",
    // One stack, one database: the specs share state, so they run one after another.
    workers: 1,
    fullyParallel: false,
    retries: Number(process.env.E2E_RETRIES ?? 0),
    reporter: [["list"], ["html", { outputFolder: ".output/report", open: "never" }]],
    use: {
        baseURL,
        locale: "tr-TR",
        video: process.env.E2E_VIDEO ? "on" : "off",
        trace: "on-first-retry",
        screenshot: "only-on-failure",
    },
    projects: [
        // Read-only specs first, on the untouched demo data...
        {
            name: "chromium",
            testMatch: ["login.spec.ts", "queue.spec.ts", "detail.spec.ts"],
            use: browser,
        },
        // ...the responsive checks (also read-only), at phone and tablet sizes...
        {
            name: "chromium-mobile",
            testMatch: ["responsive.spec.ts"],
            dependencies: ["chromium"],
            use: phone,
        },
        // ...then the ones that approve and reject demo records (they consume them).
        {
            name: "chromium-mutating",
            testMatch: ["actions.spec.ts", "bulk.spec.ts"],
            dependencies: ["chromium"],
            use: browser,
        },
    ],
});
