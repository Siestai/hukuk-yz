import { expect, test } from "@playwright/test";

import { ask, expectNoHorizontalScroll, SB001, signIn } from "./helpers";

test("login, question, clarification, conditional answer, reasoned mode, source, feedback", async ({
    page,
    isMobile,
}) => {
    await signIn(page);
    await expectNoHorizontalScroll(page);

    // B-1: the understood case and the first of five questions.
    await ask(page, SB001);
    await expect(page.getByRole("heading", { name: "Anladığım olay" })).toBeVisible();
    await expect(page.getByText("Bilinmiyor").first()).toBeVisible();
    await expect(page.getByText("Soru 1 / 6")).toBeVisible();
    await expectNoHorizontalScroll(page);

    // Two answers, the rest skipped.
    await page.getByRole("button", { name: "30 veya fazla" }).click();
    await expect(page.getByText("Soru 2 / 6")).toBeVisible();
    await page.getByRole("button", { name: "Belirsiz süreli" }).click();
    await expect(page.getByText("Soru 3 / 6")).toBeVisible();
    await page.getByRole("button", { name: "Soruları atla, koşullu cevabı göster" }).click();

    // B-2: a conditional answer, its open questions section expanded, no "müşteri" anywhere.
    await expect(page.getByText("Koşullu cevap", { exact: true })).toBeVisible();
    await expect(
        page.locator("details[open]").filter({ hasText: "Tamamlanması gereken bilgiler" }),
    ).toBeVisible();
    await expect(page.getByText(/müşteri/i)).toHaveCount(0);
    await expectNoHorizontalScroll(page);
    if (!isMobile) {
        await expect(
            page
                .getByRole("navigation", { name: "Konuşmalar" })
                .getByText("İşe iade, 5 ay kıdem")
                .first(),
        ).toBeVisible();
    }

    // B-3: the holding map.
    await page.getByRole("tab", { name: "Gerekçeli" }).click();
    await expect(page.getByRole("heading", { name: "Koşullar olaya uyuyor mu?" })).toBeVisible();
    await expectNoHorizontalScroll(page);

    // The source opens with the relied-on part highlighted.
    await page
        .getByRole("button", { name: /Dayanağı aç/ })
        .first()
        .click();
    await expect(page.locator("mark").first()).toBeVisible();
    await expectNoHorizontalScroll(page);
    if (isMobile) await page.getByRole("button", { name: "Dayanağı kapat" }).click();

    // Thumbs down, with the report form.
    await page.getByRole("button", { name: "Hatalı" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Gönder" }).click();
    await expect(page.getByText("Geri bildiriminiz alındı.")).toBeVisible();
});
