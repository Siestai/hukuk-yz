import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import { monoExt, monoLatin, sansExt, sansLatin, serifExt, serifLatin } from "../fonts/fonts";
import "./globals.css";

const fontVariables = [sansLatin, sansExt, monoLatin, monoExt, serifLatin, serifExt]
    .map((font) => font.variable)
    .join(" ");

export async function generateMetadata(): Promise<Metadata> {
    const t = await getTranslations("brand");
    return { title: t("name") };
}

export default async function RootLayout({ children }: { children: ReactNode }) {
    const locale = await getLocale();
    return (
        <html lang={locale} className={fontVariables}>
            <body>
                <NextIntlClientProvider>{children}</NextIntlClientProvider>
            </body>
        </html>
    );
}
