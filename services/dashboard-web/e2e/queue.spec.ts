import { expect, test, type Page } from "@playwright/test";

import { DEMO, openQueue, pendingTotal, queueRows } from "./helpers";

const filters = (page: Page) => page.getByRole("region", { name: "Filtreler" });

// Read-only: runs on the untouched demo data (project `chromium`).

test("the summary shows the pending records by band, reasons and results", async ({ page }) => {
    await openQueue(page);
    await expect(page.getByText(`${DEMO.total} karar onay bekliyor`)).toBeVisible();
    await expect(
        page.getByRole("img", {
            name: `Bekleyen kararların güven dağılımı: Yüksek ${DEMO.high}, Orta ${DEMO.medium}, Düşük ${DEMO.low}`,
        }),
    ).toBeVisible();
    await expect(page.getByText("En sık sebepler")).toBeVisible();
    await expect(page.getByText("Sonuçlar")).toBeVisible();
    await expect(queueRows(page)).toHaveCount(DEMO.total);
    await expect(page.getByText(`1-${DEMO.total} / ${DEMO.total}`)).toBeVisible();
});

test("the band filter changes the total and the URL", async ({ page }) => {
    await openQueue(page);
    await page.getByLabel("Güven", { exact: true }).selectOption("high");
    await expect(page).toHaveURL(/band=high/);
    await expect(queueRows(page)).toHaveCount(DEMO.high);
    await expect(page.getByText(`1-${DEMO.high} / ${DEMO.high}`)).toBeVisible();
    for (const badge of await queueRows(page).locator("td:first-child").allInnerTexts()) {
        expect(badge).toContain("Yüksek");
    }

    await page.getByLabel("Güven", { exact: true }).selectOption("low");
    await expect(page).toHaveURL(/band=low/);
    await expect(queueRows(page)).toHaveCount(DEMO.low);

    // The state is in the URL: the back button returns to the previous filter.
    await page.goBack();
    await expect(queueRows(page)).toHaveCount(DEMO.high);
});

test("a court filter and a reason filter narrow the list", async ({ page }) => {
    await openQueue(page);
    await page.getByLabel("Mahkeme", { exact: true }).selectOption("bam");
    await expect(queueRows(page)).toHaveCount(1);
    await filters(page).getByRole("link", { name: "Filtreleri temizle" }).click();
    await expect(queueRows(page)).toHaveCount(DEMO.total);

    await page.getByLabel("Sebep", { exact: true }).selectOption("date_from_closing");
    await expect(queueRows(page)).toHaveCount(1);
});

test("search finds a record by number and flags the duplicate pair", async ({ page }) => {
    await openQueue(page);
    await page.getByRole("searchbox", { name: "Esas / karar no veya başlık" }).fill("2031/1010");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/q=2031%2F1010/);
    await expect(queueRows(page)).toHaveCount(2);
    await expect(queueRows(page).getByRole("img", { name: "Mükerrer kayıt grubunda" })).toHaveCount(
        2,
    );

    await page
        .getByRole("searchbox", { name: "Esas / karar no veya başlık" })
        .fill("yok-boyle-kayit");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Bu filtrelerle kayıt yok")).toBeVisible();
    await filters(page).getByRole("link", { name: "Filtreleri temizle" }).click();
    await expect(queueRows(page)).toHaveCount(DEMO.total);
});

test("the sort order puts the most suspicious first, and can be read from the URL", async ({
    page,
}) => {
    await openQueue(page);
    await expect(queueRows(page).first().locator("td").first()).toContainText("Düşük");
    await openQueue(page, "sort=score_desc");
    await expect(queueRows(page).first().locator("td").first()).toContainText("Yüksek");
});

test("pagination shows the range, and a page past the end leads back", async ({ page }) => {
    // 12 demo records fit on one page (50), so there is one page link and no next link.
    await openQueue(page);
    const pages = page.getByRole("navigation", { name: "Sayfalar" });
    await expect(pages.getByRole("link", { name: "Sayfa 1" })).toHaveAttribute(
        "aria-current",
        "page",
    );
    await expect(pages.getByRole("link", { name: "Sonraki" })).toHaveCount(0);

    await openQueue(page, "page=2");
    await expect(page.getByText("Bu sayfada kayıt yok")).toBeVisible();
    await page.getByRole("link", { name: "İlk sayfaya dön" }).click();
    await expect(queueRows(page)).toHaveCount(DEMO.total);
    expect(await pendingTotal(page)).toBe(DEMO.total);
});
