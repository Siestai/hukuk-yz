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

// No maximum-scale: zooming stays possible. `cover` lets the page use the notch area, which the
// sticky bars pad with env(safe-area-inset-*).
export const viewport: Viewport = {
    width: "device-width",
    initialScale: 1,
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
        <html lang={locale} className={fontVariables}>
            <body>
                <NextIntlClientProvider>{children}</NextIntlClientProvider>
            </body>
        </html>
    );
}
