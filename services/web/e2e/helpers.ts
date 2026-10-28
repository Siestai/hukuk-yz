import { expect, type Page } from "@playwright/test";

/** The first question of the SB-001 fixture, word for word. */
export const SB001 =
    "5 ay kıdeme sahip bir işçi. İşe iade davası açabilir mi gerekçesi ile birlikte açıkla";

export function credentials(): { email: string; password: string } {
    const email = process.env.E2E_EMAIL;
    const password = process.env.E2E_PASSWORD;
    if (!email || !password) {
        throw new Error("Set E2E_EMAIL and E2E_PASSWORD (a user of the e2e database).");
    }
    return { email, password };
}

export async function signIn(page: Page): Promise<void> {
    const { email, password } = credentials();
    await page.goto("/giris");
    await page.getByLabel("E-posta").fill(email);
    await page.getByLabel("Parola").fill(password);
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("heading", { name: "Ne öğrenmek istiyorsunuz?" })).toBeVisible();
}

/** The page never scrolls sideways: nothing is wider than the screen. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
    const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(0);
}

export async function ask(page: Page, question: string): Promise<void> {
    await page.getByRole("textbox", { name: "Sorunuz" }).fill(question);
    await page.getByRole("button", { name: "Gönder" }).click();
}
