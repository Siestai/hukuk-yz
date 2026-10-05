import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { FlashStatus } from "@/components/flash-status";
import { HelpTip } from "@/components/help-tip";
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
import { QueueTabs } from "@/components/review-queue/queue-tabs";
import { WelcomeCard } from "@/components/review-queue/queue-welcome-card";
import { WelcomeToggle } from "@/components/review-queue/queue-welcome-toggle";
import { TopReasons } from "@/components/review-queue/top-reasons";
import { TotalsCard } from "@/components/review-queue/totals-card";
import { getReviewSummary } from "@/lib/api/review";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import {
    apiQuery,
    parseNotice,
    parseQueueParams,
    serializeQueueParams,
    statusOf,
} from "@/lib/queue-params";

const TITLE_HELP = {
    pending: "title",
    approved: "titleApproved",
    rejected: "titleRejected",
    all: "titleAll",
} as const;

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
    const approved = summary.data?.approved ?? 0;
    const rejected = summary.data?.rejected ?? 0;
    const status = statusOf(params);
    const totals = { pending, approved, rejected, all: pending + approved + rejected };
    const title = status === "pending" ? t("title") : t(`titles.${status}`);
    const subtitle =
        status === "pending"
            ? t("subtitle", { total: pending })
            : t(`subtitles.${status}`, { total: totals[status], pending, approved, rejected });

    return (
        <QueueNavigationProvider>
            <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
                <FlashStatus notice={parseNotice(search)} atQueue />
                <WelcomeCard />
                <QueueTabs params={params} counts={totals} />
                <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                    <div>
                        <div className="flex items-center gap-2">
                            <h1 className="text-xl font-semibold text-ink">{title}</h1>
                            <HelpTip name={TITLE_HELP[status]} topic={title} />
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1">
                            <p className="text-sm text-ink-2">{subtitle}</p>
                            <HelpTip
                                name={status === "pending" ? "subtitle" : "subtitleOther"}
                                topic={subtitle}
                            />
                            <WelcomeToggle />
                        </div>
                    </div>
                    <QueueActions>
                        {status === "pending" ? (
                            <Suspense fallback={<QueueBulkApprove params={params} />}>
                                <QueueBulkApprove params={params} list={list} />
                            </Suspense>
                        ) : null}
                    </QueueActions>
                </header>
                {summary.data && status === "pending" ? (
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
