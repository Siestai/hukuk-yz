import { expect, test, type Page } from "@playwright/test";

import { DEMO, openQueue, queueRows } from "./helpers";

// Read-only, on the demo data plus `infra/demo/journal_scans.py` (two scans, and Demo 09 and 10 as
// records of the first one; `make demo-data` loads it). No network: nothing here scans the site.
// The desktop tests run in project `chromium`, the `@mobile` ones in `chromium-mobile-scans`.

const SCANNED = 2;
const BADGE = "Otomatik tarama";
const scansTable = (page: Page) =>
    page.getByRole("table", { name: "Taramalar" }).locator("tbody tr");
const scanCards = (page: Page) =>
    page.getByRole("list", { name: "Taramalar" }).locator(":scope > li");
const source = (page: Page) => page.getByLabel("Kaynak", { exact: true });

async function expectNoHorizontalScroll(page: Page) {
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

async function expectTouchTarget(locator: ReturnType<Page["locator"]>) {
    const box = await locator.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
}

test("the scan list shows the seeded scans, newest first", async ({ page }) => {
    await page.goto("/taramalar");
    await expect(page.getByRole("heading", { name: "Taramalar", level: 1 })).toBeVisible();
    await expect(scansTable(page)).toHaveCount(2);
    const [latest, failed] = [scansTable(page).nth(0), scansTable(page).nth(1)];
    await expect(latest).toContainText("14.11.2026 11:00");
    await expect(latest).toContainText("Otomatik");
    await expect(latest).toContainText("Hatalarla tamamlandı");
    await expect(latest.locator("td").nth(3)).toHaveText("91");
    await expect(latest.locator("td").nth(7)).toHaveText("2");
    await expect(failed).toContainText("07.11.2026 11:00");
    await expect(failed).toContainText("Elle");
    await expect(failed).toContainText("Başarısız");
});

test("the menu leads to the scans", async ({ page }) => {
    await openQueue(page);
    await page.getByRole("complementary").getByRole("link", { name: "Taramalar" }).click();
    await expect(page).toHaveURL(/\/taramalar$/);
    await expect(page.getByRole("link", { name: "Taramalar" }).first()).toHaveAttribute(
        "aria-current",
        "page",
    );
});

test("a scan's report shows its issue, the errors in Turkish and the failure of a failed run", async ({
    page,
}) => {
    await page.goto("/taramalar");
    await scansTable(page).nth(0).getByRole("link").click();
    await expect(
        page.getByRole("heading", { name: "Tarama, 14.11.2026 11:00", level: 1 }),
    ).toBeVisible();
    const issue = page.getByRole("listitem").filter({ hasText: "91. sayı" });
    await expect(issue).toContainText("Sitedeki karar");
    await expect(
        issue.getByText("Sitedeki karar").locator("xpath=following-sibling::dd"),
    ).toHaveText("5");
    await expect(
        issue.getByText("Mükerrer adayı").locator("xpath=following-sibling::dd"),
    ).toHaveText("1");
    await expect(issue.getByText("Karar sayfasında PDF bağlantısı bulunamadı")).toBeVisible();
    await expect(issue.getByText("Site 503 hata kodu döndürdü")).toBeVisible();
    await expect(
        issue.getByRole("link", { name: "https://journal.example.test/karar-4/" }),
    ).toHaveAttribute("target", "_blank");
    await expect(page.getByText("Karşılaştırılan arşivin en yeni sayısı: 90.")).toBeVisible();

    await page.goBack();
    await scansTable(page).nth(1).getByRole("link").click();
    await expect(page.getByRole("main").getByRole("alert")).toContainText(
        "Tarama yarıda kaldı: Site 503 hata kodu döndürdü",
    );
    await expect(page.getByText("Bu taramada işlenen sayı yok.")).toBeVisible();
});

test("a scan leads to its decisions in the queue, each marked as an automatic scan", async ({
    page,
}) => {
    await page.goto("/taramalar");
    await scansTable(page).nth(0).getByRole("link").click();
    await page.getByRole("link", { name: "Bu taramadan gelen kararlar" }).click();
    await expect(page).toHaveURL(/job=[0-9a-f-]{36}/);
    await expect(page.getByRole("heading", { name: "Tüm kararlar", level: 1 })).toBeVisible();
    await expect(page.getByText("Yalnız tek bir taramanın kararları gösteriliyor.")).toBeVisible();
    const rows = page.getByRole("table", { name: "Tüm kararlar" }).locator("tbody tr");
    await expect(rows).toHaveCount(SCANNED);
    for (const row of await rows.all()) await expect(row.getByText(BADGE)).toBeVisible();

    await page.getByRole("link", { name: "Tüm kararları göster" }).click();
    await expect(page).not.toHaveURL(/job=/);
    await expect(page.getByRole("table", { name: "Tüm kararlar" }).locator("tbody tr")).toHaveCount(
        DEMO.total,
    );
});

test("the source filter switches the queue between scan, upload and archive", async ({ page }) => {
    await openQueue(page);
    await expect(queueRows(page)).toHaveCount(DEMO.total);
    await expect(queueRows(page).getByText(BADGE)).toHaveCount(SCANNED);
    await expect(source(page).locator("option")).toHaveText([
        "Tümü",
        "Otomatik tarama",
        "Yükleme",
        "Arşiv",
    ]);

    await source(page).selectOption("journal_scan");
    await expect(page).toHaveURL(/origin=journal_scan/);
    await expect(queueRows(page)).toHaveCount(SCANNED);
    await expect(queueRows(page).getByText(BADGE)).toHaveCount(SCANNED);

    await source(page).selectOption("upload");
    await expect(page).toHaveURL(/origin=upload/);
    await expect(queueRows(page)).toHaveCount(0);

    await source(page).selectOption("archive");
    await expect(page).toHaveURL(/origin=archive/);
    await expect(queueRows(page)).toHaveCount(DEMO.total - SCANNED);
    await expect(queueRows(page).getByText(BADGE)).toHaveCount(0);

    // The filter is in the URL: back returns to the previous source.
    await page.goBack();
    await expect(queueRows(page)).toHaveCount(0);
    await source(page).selectOption("");
    await expect(queueRows(page)).toHaveCount(DEMO.total);
});

test("the decision of a scan names its source and links to the journal page", async ({ page }) => {
    await openQueue(page, "origin=journal_scan");
    await queueRows(page).first().getByRole("link").click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
    await expect(page.getByText(/^Otomatik tarama, 14\.11\.2026 11:0\d, 91\. sayı$/)).toBeVisible();
    const link = page.getByRole("link", { name: "Dergi sayfası" });
    await expect(link).toHaveAttribute("href", /^https:\/\/journal\.example\.test\/karar-\d\/$/);
    await expect(link).toHaveAttribute("target", "_blank");
    await expect(link).toHaveAttribute("rel", /noopener/);

    await openQueue(page, "origin=archive");
    await queueRows(page).first().getByRole("link").click();
    await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
    await expect(page.getByText("Kaynak: Arşiv")).toBeVisible();
    await expect(page.getByRole("link", { name: "Dergi sayfası" })).toHaveCount(0);
});

test.describe("phone 360x780", () => {
    test.use({ viewport: { width: 360, height: 780 } });

    test("the scan list is cards, the report fits the screen and the links are touch targets @mobile", async ({
        page,
    }) => {
        await page.goto("/taramalar");
        await expect(page.getByRole("table")).toHaveCount(0);
        await expect(scanCards(page)).toHaveCount(2);
        await expect(scanCards(page).first()).toContainText("Hatalarla tamamlandı");
        await expect(scanCards(page).first()).toContainText("14.11.2026 11:00");
        await expectNoHorizontalScroll(page);

        await scanCards(page).first().click();
        await expect(
            page.getByRole("heading", { name: "Tarama, 14.11.2026 11:00", level: 1 }),
        ).toBeVisible();
        await expect(page.getByText("Site 503 hata kodu döndürdü")).toBeVisible();
        await expectNoHorizontalScroll(page);
        const toQueue = page.getByRole("link", { name: "Bu taramadan gelen kararlar" });
        await expectTouchTarget(toQueue);
        await toQueue.click();

        await expect(
            page.getByRole("list", { name: "Tüm kararlar" }).locator(":scope > li"),
        ).toHaveCount(SCANNED);
        await expect(page.getByRole("list", { name: "Tüm kararlar" }).getByText(BADGE)).toHaveCount(
            SCANNED,
        );
        await expectNoHorizontalScroll(page);
    });

    test("the source filter is a 16 px select of at least 44 px, and the decision's source line fits @mobile", async ({
        page,
    }) => {
        await openQueue(page);
        await page.getByRole("button", { name: /^Filtreler/ }).click();
        await expectTouchTarget(source(page));
        expect(await source(page).evaluate((element) => getComputedStyle(element).fontSize)).toBe(
            "16px",
        );
        await source(page).selectOption("journal_scan");
        await expect(page).toHaveURL(/origin=journal_scan/);
        const cards = page
            .getByRole("list", { name: "Onay bekleyen kararlar" })
            .locator(":scope > li");
        await expect(cards).toHaveCount(SCANNED);
        await expect(cards.first().getByText(BADGE)).toBeVisible();
        await expectNoHorizontalScroll(page);

        await cards.first().click();
        await page.waitForURL(/\/kararlar\/[0-9a-f-]{36}/);
        await expect(
            page.getByText(/^Otomatik tarama, 14\.11\.2026 11:0\d, 91\. sayı$/),
        ).toBeVisible();
        await expectTouchTarget(page.getByRole("link", { name: "Dergi sayfası" }));
        await expectNoHorizontalScroll(page);
    });
});
