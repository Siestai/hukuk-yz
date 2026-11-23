import { LoginForm } from "@hukuk/web-core/components/login-form";
import { safeNextPath } from "@hukuk/web-core/lib/next-path";
import { getTranslations } from "next-intl/server";

import { Wordmark } from "@/components/wordmark";

export const dynamic = "force-dynamic";

export default async function LoginPage({
    searchParams,
}: {
    searchParams: Promise<{ next?: string | string[] }>;
}) {
    const t = await getTranslations();
    const { next } = await searchParams;

    return (
        <main className="flex min-h-screen items-center justify-center p-6">
            <div className="w-full max-w-sm">
                <Wordmark className="mb-8" />
                <h1 className="font-serif text-2xl font-medium tracking-tight text-ink">
                    {t("login.title")}
                </h1>
                <p className="mb-6 mt-2 text-sm text-ink-2">{t("login.hint")}</p>
                <LoginForm next={safeNextPath(typeof next === "string" ? next : undefined)} />
            </div>
        </main>
    );
}
