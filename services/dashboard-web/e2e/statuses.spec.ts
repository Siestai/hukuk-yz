import { expect, test, type Page } from "@playwright/test";

import { openQueue, openRecord } from "./helpers";

// CONSUMES demo records: Demo 11 (rejected) and Demo 06 (approved). It runs after actions.spec
// and bulk.spec (file order), and also relies on them for the "edited" record (Demo 05) and the
// earlier rejection (Demo 12). Run `make e2e-reset` before running the suite again. The reviewer
// is the user of E2E_EMAIL; its display name is E2E_NAME (default "E2E", as in e2e/README.md).
test.describe.configure({ mode: "serial" });

const REVIEWER = process.env.E2E_NAME ?? "E2E";
const NOTE = "e2e: aynı karar başka sayıda da var.";

const tabs = (page: Page) => page.getByRole("navigation", { name: "Karar durumu" });
const rows = (page: Page, name: string) => page.getByRole("table", { name }).locator("tbody tr");

test("rejecting and approving a record moves it to its tab", async ({ page }) => {
    await openRecord(page, "Demo 11");
    await page.keyboard.press("r");
    const dialog = page.getByRole("dialog", { name: "Kararı reddet" });
    await dialog.getByLabel("Ret notu").fill(NOTE);
    await dialog.getByRole("button", { name: "Reddet" }).click();
    await expect(page).toHaveURL((url) => url.pathname === "/");

    await openRecord(page, "Demo 06");
    await page.keyboard.press("a");
    await expect(page).toHaveURL((url) => url.pathname === "/");
});

test("Reddedilen shows the note and who rejected it, and links to the detail and back", async ({
    page,
}) => {
    await openQueue(page);
    await tabs(page)
        .getByRole("link", { name: /^Reddedilen/ })
        .click();
    await expect(page).toHaveURL(/durum=reddedilen/);
    await expect(
        page.getByRole("heading", { name: "Reddedilen kararlar", level: 1 }),
    ).toBeVisible();
    await expect(tabs(page).locator('a[aria-current="page"]')).toContainText("Reddedilen");
    await expect(page.getByRole("button", { name: "Toplu onayla" })).toHaveCount(0);

    const row = rows(page, "Reddedilen kararlar").filter({ hasText: "Demo 11" });
    await expect(row).toContainText(NOTE);
    await expect(row).toContainText(REVIEWER);

    await row.getByRole("link").click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}.*durum=reddedilen/);
    const strip = page.getByRole("region", { name: "İnceleme sonucu" });
    await expect(strip).toContainText("Reddedildi");
    await expect(strip).toContainText(REVIEWER);
    await expect(strip).toContainText(NOTE);
    await expect(page.getByRole("region", { name: "İnceleme işlemleri" })).toHaveCount(0);

    await page.getByRole("link", { name: "Kuyruğa dön" }).click();
    await expect(page).toHaveURL(/durum=reddedilen/);
    await expect(
        page.getByRole("heading", { name: "Reddedilen kararlar", level: 1 }),
    ).toBeVisible();
});

test("J and K walk the list of the tab the record was opened from", async ({ page }) => {
    // Demo 12 (e2e rejection of actions.spec) and Demo 11: two rejected records, newest first.
    await openQueue(page, "durum=reddedilen");
    const list = rows(page, "Reddedilen kararlar");
    await expect(list).toHaveCount(2);
    await list.first().getByRole("link").click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
    const first = page.url();
    await page.keyboard.press("j");
    await page.waitForURL((url) => url.toString() !== first);
    expect(page.url()).toContain("durum=reddedilen");
    await page.keyboard.press("k");
    await page.waitForURL(first);
});

test("Onaylanan lists the approved records, corrected ones marked", async ({ page }) => {
    await openQueue(page, "durum=onaylanan");
    const list = rows(page, "Onaylanan kararlar");
    await expect(list.filter({ hasText: "Demo 06" })).toContainText("Onaylandı");
    await expect(list.filter({ hasText: "Demo 05" })).toContainText("Düzeltilerek onaylandı");
    await expect(list.filter({ hasText: "Demo 11" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Toplu onayla" })).toHaveCount(0);
});

test("Tümü shows all three statuses with their badges", async ({ page }) => {
    await openQueue(page, "durum=tumu");
    const list = rows(page, "Tüm kararlar");
    await expect(list.filter({ hasText: "Demo 11" })).toContainText("Reddedildi");
    await expect(list.filter({ hasText: "Demo 06" })).toContainText("Onaylandı");
    await expect(list.filter({ hasText: "Bekliyor" }).first()).toBeVisible();
    // a waiting record has no review
    await expect(list.filter({ hasText: "Bekliyor" }).first()).not.toContainText(REVIEWER);
});

test("the tabs count what the lists show", async ({ page }) => {
    await openQueue(page);
    for (const [tab, slug, name] of [
        ["Onaylanan", "onaylanan", "Onaylanan kararlar"],
        ["Reddedilen", "reddedilen", "Reddedilen kararlar"],
    ] as const) {
        const count = Number(
            (
                await tabs(page)
                    .getByRole("link", { name: new RegExp(`^${tab}`) })
                    .innerText()
            ).replace(/\D/g, ""),
        );
        await openQueue(page, `durum=${slug}`);
        await expect(rows(page, name)).toHaveCount(count);
        await openQueue(page);
    }
});
