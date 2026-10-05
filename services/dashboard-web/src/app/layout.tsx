import type { Metadata, Viewport } from "next";
import { connection } from "next/server";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { monoExt, monoLatin, sansExt, sansLatin, serifExt, serifLatin } from "../fonts/fonts";
import { THEME_COLOR } from "@/lib/theme-color";
import "./globals.css";

const fontVariables = [sansLatin, sansExt, monoLatin, monoExt, serifLatin, serifExt]
    .map((font) => font.variable)
    .join(" ");

// Next sets width=device-width and initial-scale=1 itself. No maximum-scale: zooming stays possible.
// `cover` lets the page reach under the notch and the home indicator; the mobile top bar, the
// drawer, the content column and the bottom action bar pad themselves with the safe-area insets
// (`*-safe-*` utilities of packages/ui/src/styles.css).
export const viewport: Viewport = {
    viewportFit: "cover",
    themeColor: THEME_COLOR,
};

export async function generateMetadata(): Promise<Metadata> {
    const t = await getTranslations("brand");
    return { title: t("name") };
}

export default async function RootLayout({ children }: { children: ReactNode }) {
    // Every page is rendered per request: a prerendered page (the 404) has no nonce for the CSP
    // header from proxy.ts, so its scripts would be blocked under 'strict-dynamic'.
    await connection();
    const locale = await getLocale();
    return (
        <html lang={locale} className={`${fontVariables} max-lg:scroll-pt-16 max-lg:scroll-pb-56`}>
            <body>
                <NextIntlClientProvider>{children}</NextIntlClientProvider>
            </body>
        </html>
    );
}
