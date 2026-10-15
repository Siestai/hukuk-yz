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
    const heading = TAB_HEADINGS[tab] ?? "Karar inceleme kuyruğu";
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

/** Makes the extracted text of the open decision long, as a real decision is, so the page needs scrolling. */
export async function lengthenText(page: Page): Promise<void> {
    await page.getByRole("article", { name: "Çıkarılmış karar metni" }).evaluate((article) => {
        for (let i = 0; i < 80; i++) {
            const paragraph = document.createElement("p");
            paragraph.textContent =
                `Uzun karar metni ${i}. ` + "Lorem ipsum dolor sit amet. ".repeat(12);
            article.append(paragraph);
        }
    });
}

/** A PDF with `count` pages of large text ("SAYFA n"), so a drawn page is not blank. */
export function pdfOfPages(count: number): Buffer {
    const fonts = 3;
    const objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        `<< /Type /Pages /Kids [${Array.from({ length: count }, (_, i) => `${fonts + 1 + 2 * i} 0 R`).join(" ")}] /Count ${count} >>`,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ];
    for (let i = 0; i < count; i++) {
        const stream = `BT /F1 48 Tf 50 700 Td (SAYFA ${i + 1}) Tj ET`;
        objects.push(
            `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents ${fonts + 2 + 2 * i} 0 R /Resources << /Font << /F1 3 0 R >> >> >>`,
            `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
        );
    }
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

/**
 * The PDF.js viewer in `dialog` has drawn `count` pages: one canvas each, with ink on it. A phone
 * emulated in Chromium still has the desktop PDF viewer, so an iframe proves nothing here; the
 * canvases do.
 */
export async function expectPagesDrawn(dialog: Locator, count: number): Promise<void> {
    const canvases = dialog.locator("canvas");
    await expect(canvases).toHaveCount(count);
    await expect
        .poll(() =>
            canvases.evaluateAll((all) =>
                all.map((element) => {
                    const canvas = element as HTMLCanvasElement;
                    const context = canvas.getContext("2d");
                    if (!context || canvas.width === 0) return false;
                    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
                    return data.some((value, i) => i % 4 !== 3 && value < 128);
                }),
            ),
        )
        .toEqual(Array<boolean>(count).fill(true));
}
