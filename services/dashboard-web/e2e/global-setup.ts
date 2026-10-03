import { chromium, type FullConfig } from "@playwright/test";

import { credentials } from "./helpers";
import { STORAGE_STATE } from "./playwright.config";

/** One login for the whole run (the login spec does its own); the session is kept in a file. */
export default async function globalSetup(config: FullConfig) {
    const { email, password } = credentials();
    const project = config.projects[0];
    const browser = await chromium.launch({ channel: process.env.E2E_CHANNEL || undefined });
    const context = await browser.newContext({
        baseURL: project?.use.baseURL,
        locale: "tr-TR",
    });
    const page = await context.newPage();
    await page.goto("/giris");
    await page.getByLabel("E-posta").fill(email);
    await page.getByLabel("Parola").fill(password);
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await page.waitForURL((url) => url.pathname === "/", { timeout: 20_000 });
    await context.storageState({ path: STORAGE_STATE });
    await browser.close();
}
