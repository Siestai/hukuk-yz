import { expect, test } from "@playwright/test";
import { ask, expectNoHorizontalScroll, SB001, signIn } from "./helpers";

// Run explicitly against app CHAT_BACKEND=agent and the offline real-graph server.
// The synthetic KB and scripted model check transport and persistence, not legal accuracy.
test("agent HTTP graph, clarification, answer, source and persisted feedback", async ({ page }) => {
    await signIn(page);
    await ask(page, SB001);
    await expect(page.getByRole("heading", { name: "Anladığım olay" })).toBeVisible();
    await expect(page.getByText("Soru 1 / 6")).toBeVisible();
    await page.getByRole("button", { name: "30 veya fazla", exact: true }).click();
    await page.getByRole("button", { name: "Belirsiz süreli", exact: true }).click();
    await page.getByRole("button", { name: "Soruları atla, koşullu cevabı göster" }).click();
    await expect(page.getByText("Koşullu cevap", { exact: true })).toBeVisible();
    await expect(
        page.locator("details[open]").filter({ hasText: "Tamamlanması gereken bilgiler" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Gerekçeli", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Koşullar olaya uyuyor mu?" })).toBeVisible();
    await page
        .getByRole("button", { name: /Dayanağı aç/ })
        .first()
        .click();
    await expect(page.locator("mark").first()).toBeVisible();
    await expectNoHorizontalScroll(page);
    const close = page.getByRole("button", { name: "Dayanağı kapat" });
    if (await close.isVisible()) await close.click();
    await page.getByRole("button", { name: "Hatalı", exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Gönder", exact: true }).click();
    await expect(page.getByText("Geri bildiriminiz alındı: hatalı.")).toBeVisible();
    await page.reload();
    await expect(page.getByText("Koşullu cevap", { exact: true })).toBeVisible();
    await expectNoHorizontalScroll(page);
});
