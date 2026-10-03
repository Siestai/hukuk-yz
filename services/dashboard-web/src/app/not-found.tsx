import { Button } from "@hukuk/ui";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

export default async function NotFound() {
    const t = await getTranslations("errorPage.notFound");
    return (
        <main className="flex min-h-screen items-center justify-center p-6">
            <div className="grid max-w-sm gap-4">
                <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                <p className="text-sm text-ink-2">{t("message")}</p>
                <Button asChild>
                    <Link href="/">{t("home")}</Link>
                </Button>
            </div>
        </main>
    );
}
