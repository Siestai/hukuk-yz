import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { FlashStatus } from "@/components/flash-status";
import { BandDistribution } from "@/components/review-queue/band-distribution";
import {
    QueueNavigationProvider,
    QueueResultsRegion,
} from "@/components/review-queue/queue-navigation";
import { QueueError } from "@/components/review-queue/queue-error";
import { QueueSkeleton } from "@/components/review-queue/queue-skeleton";
import { QueueTabs } from "@/components/review-queue/queue-tabs";
import { TotalsCard } from "@/components/review-queue/totals-card";
import { StatuteBulkApprove } from "@/components/statute-review/statute-bulk-approve";
import { StatuteFilters } from "@/components/statute-review/statute-filters";
import { StatuteResults } from "@/components/statute-review/statute-results";
import { StatuteTabs } from "@/components/statute-review/statute-tabs";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import { parseNotice } from "@/lib/queue-params";
import {
    parseStatuteParams,
    serializeStatuteParams,
    statuteApiQuery,
} from "@/lib/statute-queue-params";
import { summarizeStatutes } from "@/lib/statute-summary";

export default async function StatuteQueuePage({
    searchParams,
}: {
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const search = await searchParams;
    const params = parseStatuteParams(search);
    const t = await getTranslations("review.statutes");
    const api = await createServerApi();
    // The list streams into the Suspense boundary below; the summary is needed up front. If the
    // summary throws first, nobody awaits the list, so its rejection must not go unhandled.
    const list = settle(
        api.GET("/review/statutes", { params: { query: statuteApiQuery(params) } }),
        "GET /review/statutes",
    );
    list.catch(() => {});
    const summary = await settle(
        api.GET("/review/statutes/summary"),
        "GET /review/statutes/summary",
    );

    const counts = summarizeStatutes(summary.data?.items ?? [], params.statute);
    const status = params.status ?? "pending";
    const totals = {
        pending: counts.pending,
        approved: counts.approved,
        rejected: counts.rejected,
        all: counts.pending + counts.approved + counts.rejected,
    };
    const title = status === "pending" ? t("title") : t(`titles.${status}`);
    const subtitle =
        status === "pending"
            ? t("subtitle", { total: counts.pending })
            : t(`subtitles.${status}`, { total: totals[status], ...totals });

    return (
        <QueueNavigationProvider kind="statute">
            <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
                <FlashStatus notice={parseNotice(search)} atQueue subject="statute" />
                <StatuteTabs params={params} waiting={counts.waiting} />
                <QueueTabs params={params} counts={totals} />
                <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <h1 className="text-xl font-semibold text-ink">{title}</h1>
                        <p className="mt-1 text-sm text-ink-2">{subtitle}</p>
                    </div>
                    {status === "pending" ? (
                        <Suspense fallback={<StatuteBulkApprove params={params} />}>
                            <StatuteBulkApprove params={params} list={list} />
                        </Suspense>
                    ) : null}
                </header>
                {summary.data && status === "pending" ? (
                    <div className="grid gap-4 md:grid-cols-2">
                        <BandDistribution counts={counts.bands} params={params} />
                        <TotalsCard
                            approved={counts.approved}
                            rejected={counts.rejected}
                            params={params}
                        />
                    </div>
                ) : null}
                <StatuteFilters />
                <QueueResultsRegion>
                    {summary.error ? (
                        <QueueError code={summary.error.code} params={summary.error.params} />
                    ) : (
                        <Suspense
                            key={serializeStatuteParams(params).toString()}
                            fallback={<QueueSkeleton />}
                        >
                            <StatuteResults params={params} list={list} />
                        </Suspense>
                    )}
                </QueueResultsRegion>
            </main>
        </QueueNavigationProvider>
    );
}
