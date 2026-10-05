import { expect, type Locator, type Page } from "@playwright/test";

/** Demo fixture facts (infra/demo): 6 high, 4 medium, 2 low pending records, all invented. */
export const DEMO = { total: 12, high: 6, medium: 4, low: 2 } as const;

const RESET_HINT =
    "Demo data is used up or missing: run `make e2e-reset`, then `make user`, then retry.";

export function credentials(): { email: string; password: string } {
    const email = process.env.E2E_EMAIL;
    const password = process.env.E2E_PASSWORD;
    if (!email || !password) {
        throw new Error("Set E2E_EMAIL and E2E_PASSWORD (a user of the demo database).");
    }
    return { email, password };
}

/** The rows of the queue table (header excluded). */
export const queueRows = (page: Page): Locator =>
    page.getByRole("table", { name: "Onay bekleyen kararlar" }).locator("tbody tr");

/** The h1 of each queue tab (`?durum=`); the pending tab keeps the page name. */
const TAB_HEADINGS: Record<string, string> = {
    onaylanan: "Onaylanan kararlar",
    reddedilen: "Reddedilen kararlar",
    tumu: "Tüm kararlar",
};

export async function openQueue(page: Page, query = ""): Promise<void> {
    await page.goto(query ? `/?${query}` : "/");
    const tab = new URLSearchParams(query).get("durum") ?? "";
    const heading = TAB_HEADINGS[tab] ?? "İnceleme kuyruğu";
    await expect(page.getByRole("heading", { name: heading, level: 1 })).toBeVisible();
}

/** The number in "N karar onay bekliyor". */
export async function pendingTotal(page: Page): Promise<number> {
    const text = await page
        .getByText(/karar onay bekliyor/)
        .first()
        .innerText();
    return Number(text.replace(/\D/g, ""));
}

/** Opens the detail screen of the one pending record that matches `q` (title, esas or karar no). */
export async function openRecord(page: Page, q: string): Promise<void> {
    await openQueue(page, `q=${encodeURIComponent(q)}`);
    await expect(queueRows(page), RESET_HINT).toHaveCount(1);
    await queueRows(page).first().getByRole("link").click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
    await expect(page.getByRole("region", { name: "İnceleme işlemleri" })).toBeVisible();
    await waitForShortcuts(page);
}

/**
 * The server HTML shows the action bar before React has attached the keyboard shortcuts, so a key
 * pressed right after the bar appears can be lost. Wait until the page's scripts have loaded and
 * gone quiet before pressing A / E / R / J / K.
 */
export async function waitForShortcuts(page: Page): Promise<void> {
    await page.waitForLoadState("networkidle");
}

/**
 * The table is no wider than its container: `Table` wraps it in an `overflow-x-auto` box, so a
 * table that does not fit would scroll sideways inside it and hide its last columns.
 */
export async function expectTableFits(table: Locator): Promise<void> {
    const { scrollWidth, clientWidth } = await table.evaluate((element) => ({
        scrollWidth: element.scrollWidth,
        clientWidth: element.parentElement?.clientWidth ?? 0,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}
