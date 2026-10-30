import { expect, test } from "@playwright/test";

import { credentials, signIn } from "./helpers";

test("a request without a session lands on the login page", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/giris/);
    await expect(page.getByRole("heading", { name: "Giriş yap" })).toBeVisible();
});

test("a wrong password shows the Turkish error, the right one signs in and out again", async ({
    page,
}) => {
    credentials();
    await page.goto("/giris");
    // An unknown address, not the real one: failed attempts are counted per e-mail.
    await page.getByLabel("E-posta").fill(`yanlis-${Date.now()}@example.test`);
    await page.getByLabel("Parola").fill("yanlis-parola-123");
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("main").getByRole("alert")).toHaveText(
        "E-posta veya parola hatalı.",
    );

    await signIn(page);
    // The sign-out button is in the side column, or in the drawer on a phone.
    const menu = page.getByRole("button", { name: "Konuşmalar" });
    if (await menu.isVisible()) await menu.click();
    await page.getByRole("button", { name: "Çıkış yap" }).filter({ visible: true }).click();
    await expect(page).toHaveURL(/\/giris/);
    await page.goto("/");
    await expect(page).toHaveURL(/\/giris/);
});
