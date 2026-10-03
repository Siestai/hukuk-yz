import { expect, test } from "@playwright/test";

import { openQueue, queueRows } from "./helpers";

// Read-only: runs on the untouched demo data (project `chromium`). Demo 01 is a high-band
// Yargıtay 9. HD record: E. 2031/1001, K. 2031/2001.
const OPEN = "Demo 01 kidem tazminati";

async function openFirstHigh(page: import("@playwright/test").Page) {
    await openQueue(page, "band=high&q=Demo%2001");
    await queueRows(page).first().getByRole("link", { name: OPEN }).click();
    await page.waitForURL(/\/kararlar\//);
}

test("a row opens the detail screen with the extracted fields", async ({ page }) => {
    await openFirstHigh(page);
    await expect(page.getByRole("heading", { name: OPEN, level: 1 })).toBeVisible();
    await expect(page.getByText("Çıkarılan alanlar")).toBeVisible();
    await expect(page.getByText("2031/1001")).toBeVisible();
    await expect(page.getByText("2031/2001")).toBeVisible();
    await expect(page.getByText("9. HD").first()).toBeVisible();
    await expect(page.getByText("Yüksek").first()).toBeVisible();
    await expect(page.getByText("Sebep yok.")).toBeVisible();
    await expect(page.getByRole("link", { name: "Kuyruğa dön" })).toHaveAttribute(
        "href",
        /band=high/,
    );
});

test("the PDF tab holds the original file frame, served as a PDF", async ({ page }) => {
    await openFirstHigh(page);
    await expect(page.getByRole("tab", { name: "PDF" })).toHaveAttribute("aria-selected", "true");
    const frame = page.locator("iframe[title='Kararın özgün PDF\\'i']");
    await expect(frame).toBeVisible();
    const src = await frame.getAttribute("src");
    expect(src).toMatch(/^\/api\/review\/decisions\/[0-9a-f-]{36}\/file$/);
    const response = await page.request.get(src ?? "");
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/pdf");
    expect((await response.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("the text tab shows the extracted text with the editorial summary marked", async ({
    page,
}) => {
    await openFirstHigh(page);
    await page.getByRole("tab", { name: "Çıkarılmış metin" }).click();
    await expect(page.getByRole("article", { name: "Çıkarılmış karar metni" })).toContainText(
        "KURGUSAL DEMO METNİ",
    );
    await expect(page.getByRole("complementary", { name: /Dergi özeti/ })).toContainText(
        "Çalışma ve Toplum dergisinin özetidir; resmî kaynak değildir.",
    );
});

test("J and K move through the queue, K at the top says there is nothing before", async ({
    page,
}) => {
    await openQueue(page, "band=high");
    const titles = await queueRows(page).getByRole("link").allInnerTexts();
    expect(titles.length).toBeGreaterThan(2);
    await queueRows(page).first().getByRole("link").click();
    await page.waitForURL(/\/kararlar\//);
    const heading = page.getByRole("heading", { level: 1 });
    await expect(heading).toHaveText(titles[0] ?? "");

    await page.keyboard.press("k");
    await expect(page.getByText("Kuyrukta önceki kayıt yok.")).toBeVisible();

    await page.keyboard.press("j");
    await expect(heading).toHaveText(titles[1] ?? "");
    await page.keyboard.press("j");
    await expect(heading).toHaveText(titles[2] ?? "");
    await page.keyboard.press("k");
    await expect(heading).toHaveText(titles[1] ?? "");
});
