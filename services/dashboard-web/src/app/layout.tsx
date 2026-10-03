import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getTranslations } from "next-intl/server";
import type { ReactNode } from "react";

import "./globals.css";

const sans = IBM_Plex_Sans({
    subsets: ["latin", "latin-ext"],
    weight: ["400", "500", "600"],
    variable: "--font-plex-sans",
});
const mono = IBM_Plex_Mono({
    subsets: ["latin", "latin-ext"],
    weight: ["400", "500", "600"],
    variable: "--font-plex-mono",
});
const serif = IBM_Plex_Serif({
    subsets: ["latin", "latin-ext"],
    weight: ["400", "500", "600"],
    variable: "--font-plex-serif",
});

export async function generateMetadata(): Promise<Metadata> {
    const t = await getTranslations("brand");
    return { title: t("name") };
}

export default async function RootLayout({ children }: { children: ReactNode }) {
    const locale = await getLocale();
    return (
        <html lang={locale} className={`${sans.variable} ${mono.variable} ${serif.variable}`}>
            <body>
                <NextIntlClientProvider>{children}</NextIntlClientProvider>
            </body>
        </html>
    );
}
