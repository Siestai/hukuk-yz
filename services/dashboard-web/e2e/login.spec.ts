import { expect, test } from "@playwright/test";

import { credentials } from "./helpers";

// This spec signs in by hand: no stored session.
test.use({ storageState: { cookies: [], origins: [] } });

test("a request without a session lands on the login page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/giris/);
    await expect(page.getByRole("heading", { name: "Giriş yap" })).toBeVisible();
});

test("a wrong password shows the Turkish error, the right one signs in", async ({ page }) => {
    const { email, password } = credentials();
    await page.goto("/giris");

    // An unknown address, not the real one: failed attempts are counted per e-mail (5 in 15
    // minutes lock it), so repeated e2e runs must not lock the account the suite needs. The API
    // answers an unknown address and a wrong password the same way.
    await page.getByLabel("E-posta").fill(`yanlis-${Date.now()}@example.test`);
    await page.getByLabel("Parola").fill("yanlis-parola-123");
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toHaveText(
        "E-posta veya parola hatalı.",
    );
    await expect(page).toHaveURL(/\/giris/);

    await page.getByLabel("E-posta").fill(email);
    await page.getByLabel("Parola").fill(password);
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page).toHaveURL((url) => url.pathname === "/");
    await expect(page.getByRole("heading", { name: "İnceleme kuyruğu", level: 1 })).toBeVisible();
});

test("empty fields are asked for before anything is sent", async ({ page }) => {
    await page.goto("/giris");
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toHaveText(
        "E-posta ve parolayı girin.",
    );
});

test("signing out returns to the login page and closes the session", async ({ page }) => {
    const { email, password } = credentials();
    await page.goto("/giris");
    await page.getByLabel("E-posta").fill(email);
    await page.getByLabel("Parola").fill(password);
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("heading", { name: "İnceleme kuyruğu", level: 1 })).toBeVisible();

    await page.getByRole("button", { name: "Çıkış yap" }).click();
    await expect(page).toHaveURL(/\/giris/);
    await page.goto("/");
    await expect(page).toHaveURL(/\/giris/);
});
