import { expect, test, type Page } from "@playwright/test";

// Needs the worker next to the app (`make dev` starts it) and FILE_STORE_ROOT set for both. Each run
// uploads PDFs with a text of its own (a duplicate is refused), so the spec can run again on the
// same database without a reset. Project `chromium-mutating` (data changing), phone checks in
// `chromium-mobile-files` (@mobile), which reads the files of any earlier run.

const RUN = Date.now().toString(36);
const NAME = `e2e-genelge-${RUN}.pdf`;
const NEXT_NAME = `e2e-genelge-${RUN}-v2.pdf`;
const REF = `E2E/${RUN}`;
const SCAN_TIMEOUT = 90_000;

/**
 * A one-page PDF with a text layer (WinAnsi, ASCII only). The scan judges a text layer by its share
 * of Turkish function words, so the lines carry a few; without them the file would go to OCR.
 */
function pdf(token: string): Buffer {
    const lines = Array.from(
        { length: 14 },
        (_, i) =>
            `(KURGUSAL E2E DOSYASI ${token} satir ${i + 1}: bu kanun madde ile bir isci ve her isveren ya da bir daha ancak gibi) Tj T*`,
    );
    const stream = `BT /F1 11 Tf 14 TL 50 780 Td ${lines.join(" ")} ET`;
    const objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ];
    let body = "%PDF-1.4\n";
    const offsets = objects.map((object, i) => {
        const at = body.length;
        body += `${i + 1} 0 obj\n${object}\nendobj\n`;
        return at;
    });
    const xref = body.length;
    body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    body += offsets.map((at) => `${String(at).padStart(10, "0")} 00000 n \n`).join("");
    body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
    return Buffer.from(body, "latin1");
}

const attachment = (name: string, token: string) => ({
    name,
    mimeType: "application/pdf",
    buffer: pdf(token),
});

async function pick(page: Page, name: string, token: string) {
    await page.locator("input[type=file]").setInputFiles(attachment(name, token));
}

async function expectNoHorizontalScroll(page: Page) {
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

async function openList(page: Page, query = "") {
    await page.goto(`/dosyalar${query}`);
    await expect(page.getByRole("heading", { name: "Dosyalar", level: 1 })).toBeVisible();
}

const row = (page: Page, name: string) =>
    page.getByRole("table", { name: "Dosyalar" }).locator("tbody tr").filter({ hasText: name });

test.describe("files @files", () => {
    test.describe.configure({ mode: "serial" });
    test.skip(({ isMobile }) => isMobile, "the phone checks are below");

    test("a PDF is uploaded, listed, scanned, and its detail shows the text and the history", async ({
        page,
    }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        await page.setViewportSize({ width: 1440, height: 900 });
        await openList(page);
        await expect(page.getByRole("link", { name: /^Dosyalar/ })).toBeVisible();
        await pick(page, NAME, RUN);
        // Nothing has to be typed; what is typed under "Bilgileri kendim gireceğim" is sent as given.
        await page.getByRole("button", { name: "Bilgileri kendim gireceğim" }).click();
        const chosen = page.getByRole("list", { name: "Seçilen dosyalar" });
        await chosen.getByLabel("Belge türü", { exact: true }).selectOption("genelge");
        await page.getByLabel("Resmî sayı", { exact: true }).fill(REF);
        await page.getByLabel("Belge tarihi").fill("2020-06-15");
        await page.getByRole("button", { name: "Yükle", exact: true }).click();
        await expect(page.getByText("Yüklendi.")).toBeVisible();

        await openList(page, `?q=${encodeURIComponent(REF)}`);
        const listed = row(page, NAME);
        await expect(listed).toHaveCount(1);
        await expect(listed).toContainText("Genelge");
        await expect(listed).toContainText("15.06.2020");
        await expect(listed).toContainText("1 sürüm");
        // The list refreshes itself while the worker scans.
        await expect(listed.getByText("Tamamlandı")).toBeVisible({ timeout: SCAN_TIMEOUT });

        await listed.getByRole("link", { name: NAME }).click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await expect(page.getByRole("heading", { name: NAME, level: 1 })).toBeVisible();
        await expect(page.getByRole("status").filter({ hasText: "Tamamlandı" })).toBeVisible();
        await expect(page.getByText(REF).first()).toBeVisible();

        const frame = page.locator("iframe[title='Dosyanın içeriği']");
        await expect(frame).toBeVisible();
        const src = (await frame.getAttribute("src")) ?? "";
        expect(src).toMatch(/^\/api\/files\/[0-9a-f-]{36}\/content$/);
        const content = await page.request.get(src);
        expect(content.headers()["content-type"]).toContain("application/pdf");
        expect((await content.body()).subarray(0, 5).toString()).toBe("%PDF-");

        await page.getByRole("button", { name: "Metni gör" }).click();
        await expect(page.getByRole("article", { name: "Çıkarılan metin" })).toContainText(
            `KURGUSAL E2E DOSYASI ${RUN}`,
        );
        await expect(page.getByRole("list", { name: "Sürümler, eskiden yeniye" })).toContainText(
            "Sürüm 1",
        );
    });

    test("the same file again says it is already uploaded and links to the record", async ({
        page,
    }) => {
        await openList(page);
        await pick(page, `kopya-${NAME}`, RUN);
        await page.getByRole("button", { name: "Yükle", exact: true }).click();
        const alert = page.getByRole("main").getByRole("alert");
        await expect(alert).toContainText("Bu dosya zaten yüklü.");
        await alert.getByRole("link", { name: "Mevcut kaydı aç" }).click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await expect(page.getByRole("heading", { name: NAME, level: 1 })).toBeVisible();
    });

    test("a new version is linked to the file and the list keeps one row", async ({ page }) => {
        await openList(page, `?q=${encodeURIComponent(REF)}`);
        await row(page, NAME).getByRole("link", { name: NAME }).click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await page.getByRole("button", { name: "Yeni sürüm yükle" }).click();
        await pick(page, NEXT_NAME, `${RUN}-v2`);
        // Nothing is typed: the type, date and reference come from the previous version.
        await page.getByRole("button", { name: "Yükle", exact: true }).click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await expect(page.getByRole("heading", { name: NEXT_NAME, level: 1 })).toBeVisible();
        const history = page.getByRole("list", { name: "Sürümler, eskiden yeniye" });
        await expect(history.getByRole("listitem")).toHaveCount(2);
        await expect(history.getByRole("listitem").first()).toContainText(NAME);
        await expect(history.getByRole("listitem").last()).toContainText("Bu sayfa");
        await expect(page.getByText(REF).first()).toBeVisible();

        await openList(page, `?q=${encodeURIComponent(REF)}`);
        await expect(row(page, REF)).toHaveCount(1);
        await expect(row(page, NEXT_NAME)).toContainText("2 sürüm");
    });

    test("the filters narrow the list by type and by scan state", async ({ page }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        await openList(page, `?q=${encodeURIComponent(REF)}`);
        await expect(row(page, NEXT_NAME).getByText("Tamamlandı")).toBeVisible({
            timeout: SCAN_TIMEOUT,
        });
        await page.getByLabel("Belge türü", { exact: true }).selectOption("kanun");
        await expect(page.getByText("Bu filtrelere uyan dosya yok.")).toBeVisible();
        await page.getByLabel("Belge türü", { exact: true }).selectOption("genelge");
        await page.getByLabel("Tarama durumu").selectOption("done");
        await expect(row(page, NEXT_NAME)).toHaveCount(1);
    });
});

test.describe("files on a phone @mobile", () => {
    test.skip(({ isMobile }) => !isMobile, "project chromium-mobile-files only");
    test.use({ viewport: { width: 360, height: 740 } });

    test("the list shows cards and the upload zone fits the screen", async ({ page }) => {
        await openList(page, "?q=e2e-genelge-");
        const cards = page.getByRole("list", { name: "Dosyalar" }).locator(":scope > li");
        await expect(cards.first()).toBeVisible();
        await expect(page.getByRole("table")).toBeHidden();
        await expectNoHorizontalScroll(page);
        const choose = page.getByRole("button", { name: "Dosya seç" });
        expect((await choose.boundingBox())?.height).toBeGreaterThanOrEqual(44);
        await pick(page, `telefon-${NAME}`, `${RUN}-phone`);
        await expectNoHorizontalScroll(page);
        await page.getByRole("button", { name: "Bilgileri kendim gireceğim" }).click();
        await expectNoHorizontalScroll(page);
        const small = await page
            .locator("button, select, input:not([type=hidden]):not([type=file]), textarea")
            .evaluateAll((elements) =>
                elements.flatMap((element) => {
                    const { width, height } = element.getBoundingClientRect();
                    const { fontSize } = getComputedStyle(element);
                    const field = ["INPUT", "SELECT", "TEXTAREA"].includes(element.tagName);
                    return width > 0 &&
                        height > 0 &&
                        (height < 44 || (field && parseFloat(fontSize) < 16))
                        ? [
                              `${element.tagName} ${element.getAttribute("aria-label") ?? element.textContent} ${height} ${fontSize}`,
                          ]
                        : [];
                }),
            );
        expect(small).toEqual([]);
    });

    test("the detail offers a link instead of the embedded PDF", async ({ page }) => {
        await openList(page, "?q=e2e-genelge-");
        await page.getByRole("list", { name: "Dosyalar" }).getByRole("link").first().click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await expect(page.getByRole("link", { name: "Dosyayı aç" })).toBeVisible();
        await expect(page.locator("iframe[title='Dosyanın içeriği']")).toBeHidden();
        await expectNoHorizontalScroll(page);
    });
});
