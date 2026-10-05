import { expect, test, type Page } from "@playwright/test";

import { openQueue } from "./helpers";

// Read-only, projects `chromium` (mouse and keyboard) and `chromium-mobile` (touch). Every test
// starts in a fresh browser context, so the welcome card has not been closed yet.

const titleTip = (page: Page) => page.getByRole("button", { name: "Bilgi: İnceleme kuyruğu" });
const tipBox = (page: Page) => page.locator('[data-slot="info-tip-content"]');
const welcome = (page: Page) => page.getByRole("region", { name: "Libria nedir?" });

test("the title tip opens by hover with a mouse, or by a tap on a phone, and Escape closes it", async ({
    page,
    hasTouch,
}) => {
    await openQueue(page);
    await expect(tipBox(page)).toHaveCount(0);
    if (hasTouch) {
        await titleTip(page).tap();
    } else {
        await titleTip(page).hover();
    }
    await expect(tipBox(page)).toBeVisible();
    await expect(tipBox(page)).toContainText("yapay zekâ asistanı");
    await expect(titleTip(page)).toHaveAttribute("aria-expanded", "true");
    if (!hasTouch) {
        // The mouse leaving hides a box that was only hovered; a click would have pinned it.
        await page.mouse.move(0, 400);
        await expect(tipBox(page)).toHaveCount(0);
        await titleTip(page).click();
        await page.mouse.move(0, 400);
        await expect(tipBox(page)).toBeVisible();
    }
    await page.keyboard.press("Escape");
    await expect(tipBox(page)).toHaveCount(0);
    await expect(titleTip(page)).toHaveAttribute("aria-expanded", "false");
});

test("a tap or click outside closes a pinned tip", async ({ page, hasTouch }) => {
    await openQueue(page);
    if (hasTouch) {
        await titleTip(page).tap();
    } else {
        await titleTip(page).click();
    }
    await expect(tipBox(page)).toBeVisible();
    const heading = page.getByRole("heading", { name: "İnceleme kuyruğu", level: 1 });
    if (hasTouch) {
        await heading.tap();
    } else {
        await heading.click();
    }
    await expect(tipBox(page)).toHaveCount(0);
});

test("keyboard focus shows the tip", async ({ page, hasTouch }) => {
    test.skip(hasTouch, "Keyboard focus is checked with the desktop project.");
    await openQueue(page);
    await titleTip(page).focus();
    await expect(titleTip(page)).toBeFocused();
    await expect(tipBox(page)).toBeVisible();
});

for (const [name, viewport] of [
    ["phone 360x740", { width: 360, height: 740 }],
    ["tablet 768x1024", { width: 768, height: 1024 }],
    ["desktop 1440x900", { width: 1440, height: 900 }],
] as const) {
    test.describe(name, () => {
        test.use({ viewport });

        test("every tip box stays inside the screen and the page does not scroll sideways", async ({
            page,
            hasTouch,
        }) => {
            await openQueue(page);
            // The tips with the widest reach: the leftmost and the rightmost on the screen.
            const tips = page.getByRole("button", { name: /^Bilgi: / });
            const count = await tips.count();
            expect(count).toBeGreaterThan(5);
            for (const index of [0, count - 1]) {
                const tip = tips.nth(index);
                await tip.scrollIntoViewIfNeeded();
                if (hasTouch) await tip.tap();
                else await tip.click();
                await expect(tipBox(page)).toBeVisible();
                const box = await tipBox(page).boundingBox();
                expect(box).not.toBeNull();
                expect(box!.x).toBeGreaterThanOrEqual(0);
                expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width);
                // The text wraps inside the box (a nowrap table header must not leak into it).
                const text = await tipBox(page).evaluate((el) => ({
                    scrollWidth: el.scrollWidth,
                    clientWidth: el.clientWidth,
                }));
                expect(text.scrollWidth).toBeLessThanOrEqual(text.clientWidth);
                const { scrollWidth, clientWidth } = await page.evaluate(() => ({
                    scrollWidth: document.documentElement.scrollWidth,
                    clientWidth: document.documentElement.clientWidth,
                }));
                expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
                await page.keyboard.press("Escape");
                await expect(tipBox(page)).toHaveCount(0);
            }
        });
    });
}

test("a tip in a table header wraps its text inside the box", async ({ page, hasTouch }) => {
    test.skip(hasTouch, "The queue table is a desktop view.");
    await page.setViewportSize({ width: 1440, height: 900 });
    await openQueue(page);
    const tips = page.locator("thead").getByRole("button", { name: /^Bilgi: / });
    const count = await tips.count();
    expect(count).toBeGreaterThan(3);
    for (let index = 0; index < count; index++) {
        await tips.nth(index).click();
        await expect(tipBox(page)).toBeVisible();
        const text = await tipBox(page).evaluate((el) => ({
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
        }));
        expect(text.scrollWidth).toBeLessThanOrEqual(text.clientWidth);
        await page.keyboard.press("Escape");
        await expect(tipBox(page)).toHaveCount(0);
    }
});

test("the tip button is a 44 px target on a touch screen", async ({ page, hasTouch }) => {
    test.skip(!hasTouch, "The 44 px target applies to coarse pointers (phone project).");
    await openQueue(page);
    const tips = page.getByRole("button", { name: /^Bilgi: / });
    for (let index = 0; index < (await tips.count()); index++) {
        const box = await tips.nth(index).boundingBox();
        if (!box) continue; // a tip in a hidden view (the table below `lg`)
        expect(box.width).toBeGreaterThanOrEqual(44);
        expect(box.height).toBeGreaterThanOrEqual(44);
    }
});

test("the welcome card closes with 'Anladım', stays closed after a reload and comes back", async ({
    page,
}) => {
    await openQueue(page);
    await expect(welcome(page)).toBeVisible();
    await expect(welcome(page)).toContainText("yaklaşık 6.300 karar");
    await welcome(page).getByRole("button", { name: "Anladım" }).click();
    await expect(welcome(page)).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("heading", { name: "İnceleme kuyruğu", level: 1 })).toBeVisible();
    // Hydration has run by the time the toggle is interactive; the card must not have come back.
    await expect(page.getByRole("button", { name: "Bu ekran nedir?" })).toHaveAttribute(
        "aria-expanded",
        "false",
    );
    await expect(welcome(page)).toHaveCount(0);

    await page.getByRole("button", { name: "Bu ekran nedir?" }).click();
    await expect(welcome(page)).toBeVisible();
});
