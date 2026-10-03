import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { BandDistribution } from "@/components/review-queue/band-distribution";
import { QueueActions } from "@/components/review-queue/queue-actions";
import { QueueEmpty } from "@/components/review-queue/queue-empty";
import { QueueError } from "@/components/review-queue/queue-error";
import { QueueFilters } from "@/components/review-queue/queue-filters";
import { QueuePagination } from "@/components/review-queue/queue-pagination";
import { QueueTable } from "@/components/review-queue/queue-table";
import { TopReasons } from "@/components/review-queue/top-reasons";
import { TotalsCard } from "@/components/review-queue/totals-card";
import { apiError, UpstreamUnavailableError } from "@/lib/api/errors";
import { getReviewSummary } from "@/lib/api/review";
import { createServerApi } from "@/lib/api/server";
import { apiQuery, parseQueueParams } from "@/lib/queue-params";

type Answer<T> = { data?: T; error?: unknown; response: Response };

/** The data of a 2xx answer, or the API's error body of a 4xx; a lost session or a server failure throws. */
async function settle<T>(request: Promise<Answer<T>>, what: string) {
    const answer = await request.catch((cause: unknown) => {
        throw new UpstreamUnavailableError(`${what} failed: ${String(cause)}`);
    });
    const { status } = answer.response;
    if (status === 401) redirect("/oturum-sonu");
    if (status >= 500) throw new UpstreamUnavailableError(`${what} answered ${status}`);
    if (answer.data === undefined) return { error: apiError(answer.error) };
    return { data: answer.data };
}

export default async function QueuePage({
    searchParams,
}: {
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const params = parseQueueParams(await searchParams);
    const t = await getTranslations("review.queue");
    const api = await createServerApi();
    const [list, summary] = await Promise.all([
        settle(
            api.GET("/review/decisions", { params: { query: apiQuery(params) } }),
            "GET /review/decisions",
        ),
        settle(getReviewSummary(), "GET /review/decisions/summary"),
    ]);

    const failure = list.error ?? summary.error;
    const counts = {
        high: summary.data?.by_band.high ?? 0,
        medium: summary.data?.by_band.medium ?? 0,
        low: summary.data?.by_band.low ?? 0,
    };
    const pending = counts.high + counts.medium + counts.low;

    return (
        <main className="grid gap-6 p-8">
            <header className="flex items-end justify-between gap-4">
                <div>
                    <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                    <p className="mt-1 text-sm text-ink-2">{t("subtitle", { total: pending })}</p>
                </div>
                <QueueActions />
            </header>
            {summary.data ? (
                <div className="grid gap-4 lg:grid-cols-3">
                    <BandDistribution counts={counts} />
                    <TopReasons reasons={summary.data.top_reasons} />
                    <TotalsCard approved={summary.data.approved} rejected={summary.data.rejected} />
                </div>
            ) : null}
            <QueueFilters courts={Object.keys(summary.data?.by_court ?? {})} />
            {failure ? (
                <QueueError code={failure.code} params={failure.params} />
            ) : list.data && list.data.items.length > 0 ? (
                <>
                    <QueueTable items={list.data.items} />
                    <QueuePagination params={params} total={list.data.total} />
                </>
            ) : (
                <QueueEmpty params={params} pastEnd={(list.data?.total ?? 0) > 0} />
            )}
        </main>
    );
}
