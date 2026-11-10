import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { ScanResults } from "@/components/journal-scans/scan-results";
import { QueueSkeleton } from "@/components/review-queue/queue-skeleton";
import { createServerApi } from "@hukuk/web-core/api/server";
import { settle } from "@hukuk/web-core/api/settle";
import { parseScanPage, scanApiQuery } from "@/lib/journal-scans";

export default async function ScansPage({
    searchParams,
}: {
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const page = parseScanPage(await searchParams);
    const t = await getTranslations("journalScans.list");
    const api = await createServerApi();
    const list = settle(
        api.GET("/journal-scans", { params: { query: scanApiQuery(page) } }),
        "GET /journal-scans",
    );

    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <header>
                <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                <p className="mt-1 text-sm text-ink-2">{t("subtitle")}</p>
            </header>
            <Suspense key={page} fallback={<QueueSkeleton />}>
                <ScanResults page={page} list={list} />
            </Suspense>
        </main>
    );
}
