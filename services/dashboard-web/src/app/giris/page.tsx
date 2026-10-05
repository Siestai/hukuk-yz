import { Logo } from "@hukuk/ui";
import { getLocale, getTranslations } from "next-intl/server";

import { safeNextPath } from "@/lib/next-path";
import { pickQuote } from "@/lib/quotes";
import { LoginForm } from "./login-form";

// A new quote on every load: the page must not be cached.
export const dynamic = "force-dynamic";

export default async function LoginPage({
    searchParams,
}: {
    searchParams: Promise<{ next?: string | string[] }>;
}) {
    const t = await getTranslations();
    const quote = await pickQuote(await getLocale());
    const { next } = await searchParams;

    return (
        <main className="flex min-h-screen">
            <section className="hidden w-1/2 flex-col justify-between bg-primary p-12 text-primary-foreground lg:flex">
                <div className="flex items-center gap-3">
                    <Logo label={t("brand.logoLabel")} className="size-8" />
                    <div>
                        <p className="text-xl font-semibold leading-none">{t("brand.name")}</p>
                        <p className="mt-1 text-xs uppercase tracking-wide text-primary-foreground/70">
                            {t("brand.subtitle")}
                        </p>
                    </div>
                </div>
                <figure className="max-w-md">
                    <span
                        aria-hidden="true"
                        className="font-serif text-5xl text-primary-foreground/40"
                    >
                        {"“"}
                    </span>
                    <blockquote className="font-serif text-2xl leading-snug">
                        <p>{quote.text}</p>
                    </blockquote>
                    <figcaption className="mt-4 text-sm text-primary-foreground/70">
                        {"— "}
                        {quote.author}
                    </figcaption>
                </figure>
                <p className="text-sm text-primary-foreground/70">{t("login.internalNotice")}</p>
            </section>
            <section className="flex flex-1 items-center justify-center p-6">
                <div className="w-full max-w-sm">
                    <div className="mb-8 flex items-center gap-3 text-primary lg:hidden">
                        <Logo label={t("brand.logoLabel")} className="size-8" />
                        <p className="text-xl font-semibold leading-none text-ink">
                            {t("brand.name")}
                        </p>
                    </div>
                    <h1 className="text-xl font-semibold text-ink">{t("login.title")}</h1>
                    <p className="mb-6 mt-2 text-sm text-ink-2">{t("login.hint")}</p>
                    <LoginForm next={safeNextPath(typeof next === "string" ? next : undefined)} />
                </div>
            </section>
        </main>
    );
}
