import { expect, test } from "@playwright/test";

import { openQueue, openRecord, pendingTotal, queueRows } from "./helpers";

// CONSUMES demo records: Demo 12 (rejected), Demo 05 (edited and approved) and Demo 04
// (approved). Run `make db-reset demo-data` before running the suite again. The tests depend on
// each other's counts, hence serial mode. Each one narrows the queue to its record with `q`, so
// the action ends on an empty queue and the "queue finished" notice.
test.describe.configure({ mode: "serial" });

const FINISHED = "Kuyruk bitti: onay bekleyen başka kayıt yok.";

test("R opens the reject dialog, which needs a note, and rejecting ends the queue", async ({
    page,
}) => {
    await openQueue(page);
    const before = await pendingTotal(page);
    await openRecord(page, "Demo 12");

    await page.keyboard.press("r");
    const dialog = page.getByRole("dialog", { name: "Kararı reddet" });
    await expect(dialog).toBeVisible();
    const submit = dialog.getByRole("button", { name: "Reddet" });
    await expect(submit).toBeDisabled();

    await dialog.getByLabel("Ret notu").fill("e2e: karar metni yok, parser düzeltmesi gerekli.");
    await expect(submit).toBeEnabled();
    await submit.click();

    await expect(page).toHaveURL((url) => url.pathname === "/");
    const flash = page.getByRole("status").filter({ hasText: "Karar reddedildi." });
    await expect(flash).toContainText(FINISHED);
    await expect.poll(() => pendingTotal(page)).toBe(before - 1);
});

test("E edits a keyword and approving the correction ends the queue", async ({ page }) => {
    await openRecord(page, "Demo 05");

    await page.keyboard.press("e");
    const keywords = page.getByLabel("Anahtar kelimeler");
    await expect(keywords).toBeVisible();
    const original = await keywords.inputValue();
    await keywords.fill(`${original}\ne2e-anahtar`);
    await page.getByRole("button", { name: "Değişiklikleri gözden geçir" }).click();

    const dialog = page.getByRole("dialog", { name: "Düzeltmeleri onayla" });
    await expect(dialog).toContainText("Anahtar kelimeler");
    await expect(dialog).toContainText("e2e-anahtar");
    await dialog.getByLabel("Not (isteğe bağlı)").fill("e2e: anahtar kelime eklendi");
    await dialog.getByRole("button", { name: "Düzelterek onayla" }).click();

    await expect(page).toHaveURL((url) => url.pathname === "/");
    const flash = page.getByRole("status").filter({ hasText: "Karar düzeltilerek onaylandı." });
    await expect(flash).toContainText(FINISHED);
});

test("A approves the record and the queue shows the end state", async ({ page }) => {
    await openRecord(page, "Demo 04");
    await page.keyboard.press("a");

    await expect(page).toHaveURL((url) => url.pathname === "/");
    const flash = page.getByRole("status").filter({ hasText: "Karar onaylandı." });
    await expect(flash).toContainText(FINISHED);
    // The flash is one-off: it leaves the URL, the filter stays.
    await expect(page).toHaveURL(/q=Demo/);
    await expect(page).not.toHaveURL(/flash=/);
});

test("the results card counts what was approved and rejected", async ({ page }) => {
    await openQueue(page);
    const count = (label: string) =>
        page.getByText(label, { exact: true }).locator("xpath=following-sibling::dd");
    await expect(count("Onaylanan")).toHaveText("2");
    await expect(count("Reddedilen")).toHaveText("1");
    await expect(queueRows(page)).toHaveCount(9);
});
