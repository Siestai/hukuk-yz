"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { isUpstreamUnavailable } from "@/lib/api/errors";
import { useErrorMessage } from "@/lib/use-error-message";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
    const t = useTranslations("errorPage");
    const errorMessage = useErrorMessage();
    const message = errorMessage(isUpstreamUnavailable(error) ? "upstream_unavailable" : undefined);

    return (
        <main className="flex min-h-screen items-center justify-center p-6">
            <div role="alert" className="grid max-w-sm gap-4">
                <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                <p className="text-sm text-ink-2">{message}</p>
                <Button onClick={reset}>{t("retry")}</Button>
            </div>
        </main>
    );
}
