import { expect, test, type Browser, type Page } from "@playwright/test";

// Upload without a form, the approval screen, the version link and the delete flow (task 13b).
// Needs the worker next to the app and FILE_STORE_ROOT set for both, and no LLM key (the rules
// read these texts). Each run uploads texts of its own, so it can run again on the same database.
// The admin part logs in as E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD and is skipped without them.
// Project `chromium-mutating`; the phone check (@mobile) runs in `chromium-mobile-files`.

const RUN = Date.now().toString(36);
const NUMBER = (Date.now() % 900) + 100;
const REF = `2021/${NUMBER}`;
const SCAN_TIMEOUT = 90_000;
const DROP = "Dosya yükleme alanı";

const FILLER = Array.from(
    { length: 12 },
    (_, i) =>
        `${i + 1}. Bu genelge ile her işveren ve sigortalı için bir daha ancak gibi ya da bir sürenin tescil işlemleri yapılır.`,
);

/** A circular the rules read: heading, number, "Sayı" date and "Konu"; `token` makes it unique. */
function genelge(token: string, ref = REF): string {
    return [
        "T.C.",
        "SOSYAL GÜVENLİK KURUMU BAŞKANLIĞI",
        "Sigorta Primleri Genel Müdürlüğü",
        `Sayı : E-69053920-010.06.01-${token} 16.04.2021`,
        `Konu : E2E ${token} Tescil İşlemleri Hakkında`,
        "GENELGE",
        ref,
        ...FILLER,
        `Ek bilgi ${token}.`,
    ].join("\n");
}

/** Text the rules do not know: nothing is suggested. */
const plain = (token: string) =>
    [
        `Kurgusal not ${token}.`,
        ...FILLER.map((line) => line.replace("genelge", `kayıt ${token}`)),
    ].join("\n");

async function drop(page: Page, name: string, content: string) {
    const data = await page.evaluateHandle(
        ({ name, content }) => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([content], name, { type: "text/plain" }));
            return transfer;
        },
        { name, content },
    );
    await page.getByRole("group", { name: DROP }).dispatchEvent("drop", { dataTransfer: data });
}

async function openList(page: Page, query = "") {
    await page.goto(`/dosyalar${query}`);
    await expect(page.getByRole("heading", { name: "Dosyalar", level: 1 })).toBeVisible();
}

/** Drops a text, sends it, waits for the scan and opens the approval screen. */
async function uploadAndOpen(page: Page, name: string, content: string) {
    await openList(page);
    await drop(page, name, content);
    await page.getByRole("button", { name: "Yükle", exact: true }).click();
    const item = page.getByRole("list", { name: "Seçilen dosyalar" }).getByRole("listitem");
    await expect(item.getByText("Yüklendi.")).toBeVisible();
    await expect(item.getByText("Onay bekliyor")).toBeVisible({ timeout: SCAN_TIMEOUT });
    await item.getByRole("link", { name: "İncele ve onayla" }).click();
    await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
}

const panel = (page: Page) => page.getByRole("region", { name: "Onay bekliyor" });

async function login(
    browser: Browser,
    baseURL: string | undefined,
    email: string,
    password: string,
) {
    const context = await browser.newContext({ baseURL, locale: "tr-TR", storageState: undefined });
    const page = await context.newPage();
    await page.goto("/giris");
    await page.getByLabel("E-posta").fill(email);
    await page.getByLabel("Parola").fill(password);
    await page.getByRole("button", { name: "Giriş yap" }).click();
    await page.waitForURL((url) => url.pathname === "/", { timeout: 20_000 });
    return { context, page };
}

test.describe("file approval @files", () => {
    test.describe.configure({ mode: "serial" });
    test.skip(({ isMobile }) => isMobile, "the phone check is below");

    const FIRST = `e2e-onay-${RUN}.txt`;
    const SECOND = `e2e-onay-${RUN}-v2.txt`;
    let firstUrl = "";

    test("a dropped file is scanned, suggested with its evidence, corrected and approved", async ({
        page,
    }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        await page.setViewportSize({ width: 1440, height: 900 });
        await uploadAndOpen(page, FIRST, genelge(RUN));
        firstUrl = page.url();

        const form = panel(page);
        await expect(form.getByLabel("Belge türü (zorunlu)")).toHaveValue("genelge");
        await expect(form.getByLabel("Resmî sayı")).toHaveValue(REF);
        await expect(form.getByLabel("Belge tarihi")).toHaveValue("2021-04-16");
        await expect(form.getByText("Metinden okundu").first()).toBeVisible();
        await expect(form.getByText(`1. sayfa: 'GENELGE ${REF}'`)).toBeVisible();
        await expect(form.getByText("1. sayfa: '16.04.2021'")).toBeVisible();
        const approve = form.getByRole("button", { name: "Onayla" });
        await expect(approve).toBeEnabled();

        // One field is corrected: it becomes the user's own value.
        await form.getByLabel("Belge tarihi").fill("2021-04-17");
        await expect(form.getByText("Siz girdiniz").first()).toBeVisible();
        await approve.click();
        await expect(panel(page)).toHaveCount(0);
        await expect(page.getByText("Onaylı").first()).toBeVisible();
        await expect(page.getByText("17.04.2021").first()).toBeVisible();

        await openList(page, `?q=${encodeURIComponent(FIRST)}`);
        const row = page
            .getByRole("table", { name: "Dosyalar" })
            .locator("tbody tr")
            .filter({ hasText: FIRST });
        await expect(row.getByText("Onaylı")).toBeVisible();
        await expect(row).toContainText("17.04.2021");
        await openList(page, `?onay=bekliyor&q=${encodeURIComponent(FIRST)}`);
        await expect(page.getByText("Bu filtrelere uyan dosya yok.")).toBeVisible();
    });

    test("a file with the same number is offered as the next version and linked", async ({
        page,
    }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        await uploadAndOpen(page, SECOND, genelge(`${RUN}-2`));
        const form = panel(page);
        await expect(form.getByText(`Bu, ${FIRST} dosyasının yeni sürümü olabilir`)).toBeVisible();
        await expect(form.getByLabel("Ayrı belge olarak kaydet")).toBeChecked();
        await expect(form.getByText("Şu dosyalara çok benziyor:")).toBeVisible();
        const similar = form.getByRole("link", { name: new RegExp(`^${FIRST} \\(benzerlik`) });
        await expect(similar).toHaveAttribute("target", "_blank");
        await form.getByLabel("Yeni sürüm olarak bağla").check();
        await form.getByRole("button", { name: "Onayla" }).click();
        await expect(panel(page)).toHaveCount(0);
        const history = page.getByRole("list", { name: "Sürümler, eskiden yeniye" });
        await expect(history.getByRole("listitem")).toHaveCount(2);
        await expect(history.getByRole("listitem").first()).toContainText(FIRST);

        // The first file now has a newer version: it is no longer a row of the list.
        await page.goto(firstUrl);
        await expect(page.getByText("Bu, belgenin eski bir sürümü.")).toBeVisible();
    });

    test("a pending file is deleted after the question; the count follows", async ({ page }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        const name = `e2e-sil-${RUN}.txt`;
        await uploadAndOpen(page, name, plain(`sil-${RUN}`));
        const url = page.url();
        await expect(panel(page).getByText("Dosyadan öneri çıkarılamadı")).toBeVisible();
        // No type, no approval.
        await expect(panel(page).getByRole("button", { name: "Onayla" })).toBeDisabled();

        await openList(page, "?onay=bekliyor");
        const waiting = page.getByRole("navigation", { name: "Onay durumu" });
        await expect(waiting.getByRole("link", { name: /Onay bekliyor/ })).toHaveAttribute(
            "aria-current",
            "page",
        );
        await expect(page.getByRole("link", { name: name }).first()).toBeVisible();
        await expect(
            page
                .getByRole("navigation", { name: "Ana menü" })
                .getByRole("link", { name: /Dosyalar/ }),
        ).toContainText("onay bekleyen dosya");

        await page.goto(url);
        await panel(page).getByRole("button", { name: "Sil" }).click();
        const dialog = page.getByRole("dialog", { name: "Dosya silinsin mi?" });
        await dialog.getByRole("button", { name: "Vazgeç" }).click();
        await expect(dialog).toBeHidden();
        await panel(page).getByRole("button", { name: "Sil" }).click();
        await page.getByRole("dialog").getByRole("button", { name: "Sil" }).click();
        await page.waitForURL((u) => u.pathname === "/dosyalar");
        await openList(page, `?q=${encodeURIComponent(name)}`);
        await expect(page.getByText("Bu filtrelere uyan dosya yok.")).toBeVisible();
        const gone = await page.request.get(`/api/files/${url.split("/").pop()}`);
        expect(gone.status()).toBe(404);
    });

    test("an approved file is deleted only after an admin takes the approval back", async ({
        page,
        browser,
        baseURL,
    }) => {
        test.skip(
            !process.env.E2E_ADMIN_EMAIL || !process.env.E2E_ADMIN_PASSWORD,
            "set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD (an admin of the demo database)",
        );
        test.setTimeout(SCAN_TIMEOUT + 90_000);
        const name = `e2e-admin-${RUN}.txt`;
        await uploadAndOpen(page, name, genelge(`${RUN}-admin`, `2022/${NUMBER}`));
        const url = page.url();
        await panel(page).getByRole("button", { name: "Onayla" }).click();
        await expect(panel(page)).toHaveCount(0);
        // An approved file has no Sil, and a reviewer cannot take the approval back.
        await expect(page.getByRole("button", { name: "Sil" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Onayı kaldır" })).toHaveCount(0);

        const admin = await login(
            browser,
            baseURL,
            process.env.E2E_ADMIN_EMAIL ?? "",
            process.env.E2E_ADMIN_PASSWORD ?? "",
        );
        try {
            await admin.page.goto(url);
            await expect(admin.page.getByRole("button", { name: "Sil" })).toHaveCount(0);
            await admin.page.getByRole("button", { name: "Onayı kaldır" }).click();
            await expect(panel(admin.page)).toBeVisible();
            await panel(admin.page).getByRole("button", { name: "Sil" }).click();
            await admin.page.getByRole("dialog").getByRole("button", { name: "Sil" }).click();
            await admin.page.waitForURL((u) => u.pathname === "/dosyalar");
            const gone = await admin.page.request.get(`/api/files/${url.split("/").pop()}`);
            expect(gone.status()).toBe(404);
        } finally {
            await admin.context.close();
        }
    });
});

test.describe("file approval on a phone @mobile", () => {
    test.skip(({ isMobile }) => !isMobile, "project chromium-mobile-files only");
    test.use({ viewport: { width: 360, height: 740 } });

    test("the upload list, the approval screen and the pending tab fit the screen", async ({
        page,
    }) => {
        test.setTimeout(SCAN_TIMEOUT + 60_000);
        const name = `e2e-telefon-${RUN}.txt`;
        await openList(page);
        await drop(page, name, genelge(`${RUN}-phone`, `2023/${NUMBER}`));
        await page.getByRole("button", { name: "Yükle", exact: true }).click();
        const item = page.getByRole("list", { name: "Seçilen dosyalar" }).getByRole("listitem");
        await expect(item.getByText("Onay bekliyor")).toBeVisible({ timeout: SCAN_TIMEOUT });
        await expectFits(page);
        await item.getByRole("link", { name: "İncele ve onayla" }).click();
        await page.waitForURL(/\/dosyalar\/[0-9a-f-]{36}$/);
        await expect(panel(page).getByLabel("Belge türü (zorunlu)")).toHaveValue("genelge");
        await expectFits(page);
        const small = await panel(page)
            .locator("button, select, input:not([type=hidden]), textarea")
            .evaluateAll((elements) =>
                elements.flatMap((element) => {
                    const { width, height } = element.getBoundingClientRect();
                    const { fontSize } = getComputedStyle(element);
                    const field = ["INPUT", "SELECT", "TEXTAREA"].includes(element.tagName);
                    return width > 0 &&
                        height > 0 &&
                        (height < 44 || (field && parseFloat(fontSize) < 16))
                        ? [`${element.tagName} ${element.textContent} ${height} ${fontSize}`]
                        : [];
                }),
            );
        expect(small).toEqual([]);

        await openList(page, "?onay=bekliyor");
        await expect(
            page.getByRole("list", { name: "Dosyalar" }).locator(":scope > li").first(),
        ).toBeVisible();
        await expect(page.getByRole("table")).toBeHidden();
        await expectFits(page);
    });
});

async function expectFits(page: Page) {
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}
