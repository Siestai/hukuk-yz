import { notFound } from "next/navigation";

import { FlashStatus } from "@/components/flash-status";
import { ActionBar } from "@/components/review-detail/action-bar";
import { HistoryCard } from "@/components/review-detail/history-card";
import { ReviewProvider } from "@/components/review-detail/review-session";
import { ReviewStatusStrip } from "@/components/review-detail/review-status-strip";
import { LiveNotice } from "@/components/statute-review/live-notice";
import { StatuteConfidenceCard } from "@/components/statute-review/statute-confidence-card";
import { StatuteHeader } from "@/components/statute-review/statute-header";
import { TimelineExplorer } from "@/components/statute-review/timeline-explorer";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import { parseNotice, parsePosition } from "@/lib/queue-params";
import { parseStatuteParams } from "@/lib/statute-queue-params";
import { isUuid } from "@/lib/uuid";

/** The status strip speaks the source vocabulary: a pending article is "in review", the rest left the queue. */
const STRIP_STATUS = {
    pending: "analyzed",
    approved: "published",
    rejected: "rejected",
    superseded: "superseded",
} as const;

export default async function StatuteArticlePage({
    params,
    searchParams,
}: {
    params: Promise<{ extractionId: string }>;
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const { extractionId } = await params;
    if (!isUuid(extractionId)) notFound();
    const search = await searchParams;
    const queue = parseStatuteParams(search);
    const api = await createServerApi();
    const result = await settle(
        api.GET("/review/statutes/{extraction_id}", {
            params: { path: { extraction_id: extractionId } },
        }),
        "GET /review/statutes/{id}",
    );
    if (result.error) {
        if (result.error.code === "extraction_not_found") notFound();
        throw new Error(`GET /review/statutes/{id} answered ${result.error.code ?? "an error"}`);
    }
    const detail = result.data;

    return (
        <ReviewProvider
            key={extractionId}
            extractionId={extractionId}
            queue={queue}
            pos={parsePosition(search)}
            canAct={detail.status === "pending"}
        >
            <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
                <FlashStatus notice={parseNotice(search)} atQueue={false} subject="statute" />
                <StatuteHeader
                    statuteNumber={detail.statute_number}
                    statuteTitle={detail.statute_title}
                    articleNo={detail.article_no}
                    heading={detail.heading}
                    band={detail.band}
                    status={detail.status}
                    latestSnapshotDate={detail.latest_snapshot_date}
                    queue={queue}
                />
                <ReviewStatusStrip
                    sourceStatus={STRIP_STATUS[detail.status]}
                    reviews={detail.reviews}
                />
                {detail.live_extraction_id ? (
                    <LiveNotice id={detail.live_extraction_id} queue={queue} />
                ) : null}
                <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
                    <StatuteConfidenceCard
                        band={detail.band}
                        reasons={detail.reasons}
                        warnings={detail.warnings}
                    />
                    <HistoryCard reviews={detail.reviews} />
                </div>
                <TimelineExplorer
                    timeline={detail.timeline}
                    latestSnapshotDate={detail.latest_snapshot_date}
                />
                <ActionBar editable={false} />
            </main>
        </ReviewProvider>
    );
}
