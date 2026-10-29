import { defineConfig, devices } from "@playwright/test";

// Runs against a live stack: `app` with CHAT_BACKEND=fixture and this app (e2e/README.md); CI has none.
// Credentials come from the environment and are never committed. 3000 is where `pnpm start` listens;
// the dashboard defaults to it too, so with both running start this one with PORT and set BASE_URL.
const baseURL = process.env.BASE_URL ?? "http://localhost:3000";
const channel = process.env.E2E_CHANNEL || undefined;

export default defineConfig({
    testDir: ".",
    outputDir: ".output/results",
    // One stack, one in-memory chat store: the specs run one after another.
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
        { name: "chromium", use: { ...devices["Desktop Chrome"], channel } },
        // A phone: Chromium with touch and mobile emulation, so `pointer: coarse` matches.
        { name: "chromium-mobile", use: { ...devices["Pixel 7"], channel } },
    ],
});
