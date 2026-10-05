import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { FlashStatus } from "@/components/flash-status";
import { BandDistribution } from "@/components/review-queue/band-distribution";
import { QueueBulkApprove } from "@/components/review-queue/queue-bulk-approve";
import { QueueActions } from "@/components/review-queue/queue-actions";
import { QueueError } from "@/components/review-queue/queue-error";
import { QueueFilters } from "@/components/review-queue/queue-filters";
import {
    QueueNavigationProvider,
    QueueResultsRegion,
} from "@/components/review-queue/queue-navigation";
import { QueueResults } from "@/components/review-queue/queue-results";
import { QueueSkeleton } from "@/components/review-queue/queue-skeleton";
import { TopReasons } from "@/components/review-queue/top-reasons";
import { TotalsCard } from "@/components/review-queue/totals-card";
import { getReviewSummary } from "@/lib/api/review";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import { apiQuery, parseNotice, parseQueueParams, serializeQueueParams } from "@/lib/queue-params";

export default async function QueuePage({
    searchParams,
}: {
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const search = await searchParams;
    const params = parseQueueParams(search);
    const t = await getTranslations("review.queue");
    const api = await createServerApi();
    // The list streams into the Suspense boundary below; the summary is needed up front. If the
    // summary throws first, nobody awaits the list, so its rejection must not go unhandled.
    const list = settle(
        api.GET("/review/decisions", { params: { query: apiQuery(params) } }),
        "GET /review/decisions",
    );
    list.catch(() => {});
    const summary = await settle(getReviewSummary(), "GET /review/decisions/summary");

    const counts = {
        high: summary.data?.by_band.high ?? 0,
        medium: summary.data?.by_band.medium ?? 0,
        low: summary.data?.by_band.low ?? 0,
    };
    const pending = counts.high + counts.medium + counts.low;

    return (
        <QueueNavigationProvider>
            <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
                <FlashStatus notice={parseNotice(search)} atQueue />
                <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                        <p className="mt-1 text-sm text-ink-2">
                            {t("subtitle", { total: pending })}
                        </p>
                    </div>
                    <QueueActions>
                        <Suspense fallback={<QueueBulkApprove params={params} />}>
                            <QueueBulkApprove params={params} list={list} />
                        </Suspense>
                    </QueueActions>
                </header>
                {summary.data ? (
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        <BandDistribution counts={counts} params={params} />
                        <TopReasons reasons={summary.data.top_reasons} params={params} />
                        <TotalsCard
                            approved={summary.data.approved}
                            rejected={summary.data.rejected}
                        />
                    </div>
                ) : null}
                <QueueFilters courts={Object.keys(summary.data?.by_court ?? {})} />
                <QueueResultsRegion>
                    {summary.error ? (
                        <QueueError code={summary.error.code} params={summary.error.params} />
                    ) : (
                        <Suspense
                            key={serializeQueueParams(params).toString()}
                            fallback={<QueueSkeleton />}
                        >
                            <QueueResults params={params} list={list} />
                        </Suspense>
                    )}
                </QueueResultsRegion>
            </main>
        </QueueNavigationProvider>
    );
}
