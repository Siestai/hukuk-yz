import { expect, test, type Page } from "@playwright/test";

import { openQueue } from "./helpers";

// Read-only, project `chromium-mobile` (Pixel 7: touch, so `pointer: coarse`). The viewport is
// set per block: 360x740 is the small phone, 768x1024 the tablet (`md`, below `lg`: cards in two columns, no table).

const PHONE = { width: 360, height: 740 };
const TABLET = { width: 768, height: 1024 };

const cards = (page: Page) =>
    page.getByRole("list", { name: "Onay bekleyen kararlar" }).getByRole("listitem");
const pdfLink = (page: Page) => page.getByRole("link", { name: "PDF'i yeni sekmede aç" });
const menuButton = (page: Page) => page.getByRole("button", { name: "Menü", exact: true });
const pdfFrame = (page: Page) => page.getByTitle("Kararın özgün PDF'i");

/** The page is no wider than the screen: nothing makes the document scroll sideways. */
async function expectNoHorizontalScroll(page: Page) {
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

/** Opens the first record of the queue from its card (the table only exists from `lg`). */
async function openFirstRecord(page: Page) {
    await openQueue(page);
    await cards(page).first().click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
    await expect(page.getByRole("region", { name: "İnceleme işlemleri" })).toBeVisible();
}

for (const [name, viewport, phone] of [
    ["phone 360x740", PHONE, true],
    ["tablet 768x1024", TABLET, false],
] as const) {
    test.describe(name, () => {
        test.use({ viewport });

        test("the login page does not scroll sideways", async ({ browser, baseURL }) => {
            const context = await browser.newContext({
                baseURL,
                viewport,
                locale: "tr-TR",
                storageState: { cookies: [], origins: [] },
            });
            const page = await context.newPage();
            await page.goto("/giris");
            await expect(page.getByRole("heading", { name: "Giriş yap" })).toBeVisible();
            // Below `lg` the left panel is gone and the brand sits above the form.
            await expect(page.getByRole("img", { name: "Libria logosu" })).toBeVisible();
            await expectNoHorizontalScroll(page);
            await context.close();
        });

        test("the queue does not scroll sideways", async ({ page }) => {
            await openQueue(page);
            await expectNoHorizontalScroll(page);
        });

        test("the detail screen does not scroll sideways", async ({ page }) => {
            await openFirstRecord(page);
            await expectNoHorizontalScroll(page);
        });

        test("the PDF is a link on a phone and a frame from md up", async ({ page }) => {
            await openFirstRecord(page);
            if (phone) {
                await expect(pdfLink(page)).toBeVisible();
                await expect(pdfLink(page)).toHaveAttribute("target", "_blank");
                await expect(pdfLink(page)).toHaveAttribute("href", /\/file$/);
                await expect(pdfFrame(page)).toBeHidden();
            } else {
                await expect(pdfLink(page)).toBeHidden();
                await expect(pdfFrame(page)).toBeVisible();
            }
        });
    });
}

test.describe("tablet 768x1024", () => {
    test.use({ viewport: TABLET });

    test("the queue shows cards in two columns, not the table", async ({ page }) => {
        await openQueue(page);
        await expect(page.getByRole("table")).toHaveCount(0);
        const [first, second] = await Promise.all([
            cards(page).nth(0).boundingBox(),
            cards(page).nth(1).boundingBox(),
        ]);
        expect(second?.y).toBe(first?.y);
        expect(second?.x ?? 0).toBeGreaterThan(first?.x ?? 0);
    });
});

test.describe("phone 360x740", () => {
    test.use({ viewport: PHONE });

    test("the file route is not requested while only the PDF link is shown", async ({ page }) => {
        const urls: string[] = [];
        page.on("request", (request) => urls.push(request.url()));
        await openFirstRecord(page);
        await expect(pdfLink(page)).toBeVisible();
        await page.waitForLoadState("networkidle");
        expect(urls.filter((url) => /\/decisions\/[^/]+\/file/.test(url))).toEqual([]);
    });

    test("the drawer closes when the screen grows to lg, and the side nav works", async ({
        page,
    }) => {
        await openQueue(page);
        await menuButton(page).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.setViewportSize({ width: 1280, height: 800 });
        await expect(page.getByRole("dialog")).toHaveCount(0);
        const link = page
            .getByRole("complementary")
            .getByRole("link", { name: /İnceleme kuyruğu/ });
        await expect(link).toBeVisible();
        await link.click();
        await expect(page).toHaveURL(/\/$/);
    });

    test("the queue shows cards, not the table, and a card opens the record", async ({ page }) => {
        await openQueue(page);
        await expect(page.getByRole("table")).toHaveCount(0);
        await expect(cards(page).first()).toBeVisible();
        await cards(page).first().click();
        await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    });

    test("the menu drawer opens, takes the user to the queue and closes", async ({ page }) => {
        await openFirstRecord(page);
        const menu = menuButton(page);
        await expect(menu).toHaveAttribute("aria-expanded", "false");
        await menu.click();
        const drawer = page.getByRole("dialog", { name: "Menü" });
        await expect(drawer).toBeVisible();
        await expect(menu).toHaveAttribute("aria-expanded", "true");
        await drawer.getByRole("link", { name: /İnceleme kuyruğu/ }).click();
        await expect(page).toHaveURL(/\/$/);
        await expect(drawer).toBeHidden();
        await expect(
            page.getByRole("heading", { name: "İnceleme kuyruğu", level: 1 }),
        ).toBeVisible();
    });

    test("Escape closes the drawer and the focus returns to the menu button", async ({ page }) => {
        await openQueue(page);
        const menu = menuButton(page);
        await menu.click();
        await expect(page.getByRole("dialog", { name: "Menü" })).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(page.getByRole("dialog")).toBeHidden();
        await expect(menu).toBeFocused();
    });

    test("the filters sit behind a toggle that opens them", async ({ page }) => {
        await openQueue(page);
        const toggle = page.getByRole("button", { name: /^Filtreler/ });
        await expect(toggle).toHaveAttribute("aria-expanded", "false");
        await expect(page.getByLabel("Güven", { exact: true })).toBeHidden();
        await toggle.click();
        await expect(page.getByLabel("Güven", { exact: true })).toBeVisible();
    });

    test("the bulk approve button is reachable and opens its dialog inside the screen", async ({
        page,
    }) => {
        await openQueue(page, "band=high");
        const button = page.getByRole("button", { name: "Toplu onayla" });
        await button.scrollIntoViewIfNeeded();
        await expect(button).toBeEnabled();
        await button.click();
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        const box = await dialog.boundingBox();
        expect(box?.x).toBeGreaterThanOrEqual(0);
        expect((box?.x ?? 0) + (box?.width ?? 0)).toBeLessThanOrEqual(PHONE.width);
        await expectNoHorizontalScroll(page);
        await page.keyboard.press("Escape");
        await expect(dialog).toBeHidden();
    });

    test("the action bar is on screen, in one row, and covers no content at the end", async ({
        page,
    }) => {
        await openFirstRecord(page);
        const bar = page.getByRole("region", { name: "İnceleme işlemleri" });
        await expect(bar).toBeInViewport();
        const buttons = await bar.getByRole("button").all();
        expect(buttons).toHaveLength(3);
        const tops = await Promise.all(buttons.map(async (b) => (await b.boundingBox())?.y));
        expect(new Set(tops).size).toBe(1);
        // The keyboard hints are for desktops.
        await expect(bar.locator("kbd").first()).toBeHidden();

        await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
        // The last content of the page is the document panel (a single column on a phone).
        const last = page.getByRole("tabpanel");
        const [lastBox, barBox] = await Promise.all([last.boundingBox(), bar.boundingBox()]);
        expect((lastBox?.y ?? 0) + (lastBox?.height ?? 0)).toBeLessThanOrEqual(barBox?.y ?? 0);
        await expectNoHorizontalScroll(page);
    });

    test("the field labels are stacked over their values, not broken letter by letter", async ({
        page,
    }) => {
        await openFirstRecord(page);
        const label = page.locator("dt").first();
        const value = page.locator("dd").first();
        const [labelBox, valueBox] = await Promise.all([label.boundingBox(), value.boundingBox()]);
        expect((valueBox?.y ?? 0) >= (labelBox?.y ?? 0) + (labelBox?.height ?? 0) - 1).toBe(true);
        expect(labelBox?.height).toBeLessThan(30);
    });

    test("touch targets are at least 44 px high", async ({ page }) => {
        await openQueue(page);
        await page.getByRole("button", { name: /^Filtreler/ }).click();
        const small = await page
            .locator("button, select, input:not([type=hidden]), summary, [role=tab]")
            .evaluateAll((elements) =>
                elements.flatMap((element) => {
                    const { width, height } = element.getBoundingClientRect();
                    return width > 0 && height > 0 && height < 44
                        ? [
                              `${element.tagName} ${element.getAttribute("aria-label") ?? element.textContent} ${height}`,
                          ]
                        : [];
                }),
            );
        expect(small).toEqual([]);
    });
});
