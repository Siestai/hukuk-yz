import { expect, test } from "@playwright/test";

import { openQueue, pendingTotal, queueRows } from "./helpers";

// CONSUMES demo records: the high-band records Demo 01-03 (karar no 2031/2001-2003). Run
// `make db-reset demo-data` before running the suite again. The search `2031/200` also matches
// Demo 07 (K. 2031/2007), which is medium band and so stays out of the high-band bulk run.
const SEARCH = "2031/200";

test("bulk approve needs the high band; with it, the narrowed list is approved and reported", async ({
    page,
}) => {
    await openQueue(page, `q=${encodeURIComponent(SEARCH)}`);
    const before = await pendingTotal(page);
    const open = page.getByRole("button", { name: "Toplu onayla", exact: true });
    await expect(open).toBeDisabled();

    await page.getByLabel("Güven", { exact: true }).selectOption("high");
    await expect(queueRows(page)).toHaveCount(3);
    await expect(open).toBeEnabled();
    await open.click();

    const dialog = page.getByRole("dialog", { name: "Yüksek güven bandını toplu onayla" });
    await expect(dialog).toContainText("3 karar");
    await expect(dialog).toContainText("Arama: 2031/200");
    const start = dialog.getByRole("button", { name: "Onayı başlat" });
    await expect(start).toBeDisabled();
    await dialog.getByLabel("Bu 3 kaydı kendi adımla onaylıyorum").check();
    await expect(start).toBeEnabled();
    await start.click();

    await expect(dialog.getByRole("heading", { name: "Toplu onay tamamlandı" })).toBeVisible();
    await expect(dialog.getByText("3 / 3")).toBeVisible();
    await expect(dialog.getByText("Yayınlanan").locator("xpath=following-sibling::dd")).toHaveText(
        "3",
    );
    await expect(dialog.getByText("Çakışan").locator("xpath=following-sibling::dd")).toHaveText(
        "0",
    );
    await expect(dialog.getByText("Başarısız").locator("xpath=following-sibling::dd")).toHaveText(
        "0",
    );

    await dialog.getByRole("button", { name: "Kapat" }).click();
    await expect(dialog).toBeHidden();
    await expect(page.getByText("Bu filtrelerle kayıt yok")).toBeVisible();
    await expect.poll(() => pendingTotal(page)).toBe(before - 3);
});
