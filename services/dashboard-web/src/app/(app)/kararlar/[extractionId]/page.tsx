import { notFound } from "next/navigation";

import { FlashStatus } from "@/components/flash-status";
import { ActionBar } from "@/components/review-detail/action-bar";
import { ConfidenceCard } from "@/components/review-detail/confidence-card";
import { DecisionHeader } from "@/components/review-detail/decision-header";
import { DocumentTabs } from "@/components/review-detail/document-tabs";
import { DuplicatesCard } from "@/components/review-detail/duplicates-card";
import { FieldsPanel } from "@/components/review-detail/fields-panel";
import { HistoryCard } from "@/components/review-detail/history-card";
import { ReviewProvider } from "@/components/review-detail/review-session";
import { TextPanel } from "@/components/review-detail/text-panel";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import { readFields } from "@/lib/decision-fields";
import { parseNotice, parsePosition, parseQueueParams } from "@/lib/queue-params";
import { isUuid } from "@/lib/uuid";

export default async function DecisionPage({
    params,
    searchParams,
}: {
    params: Promise<{ extractionId: string }>;
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const { extractionId } = await params;
    if (!isUuid(extractionId)) notFound();
    const search = await searchParams;
    const queue = parseQueueParams(search);
    const api = await createServerApi();
    const result = await settle(
        api.GET("/review/decisions/{extraction_id}", {
            params: { path: { extraction_id: extractionId } },
        }),
        "GET /review/decisions/{id}",
    );
    if (result.error) {
        if (result.error.code === "extraction_not_found") notFound();
        throw new Error(`GET /review/decisions/{id} answered ${result.error.code ?? "an error"}`);
    }
    const detail = result.data;
    const fields = readFields(detail.fields);

    return (
        <ReviewProvider
            key={extractionId}
            extractionId={extractionId}
            queue={queue}
            pos={parsePosition(search)}
            canAct={detail.source_status === "analyzed"}
        >
            <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
                <FlashStatus notice={parseNotice(search)} atQueue={false} />
                <DecisionHeader
                    title={detail.title}
                    band={detail.confidence.band}
                    score={detail.confidence.score}
                    sourceStatus={detail.source_status}
                    queue={queue}
                />
                <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2">
                    <div className="grid grid-cols-1 gap-4">
                        <FieldsPanel fields={fields} />
                        <ConfidenceCard
                            score={detail.confidence.score}
                            band={detail.confidence.band}
                            reasons={detail.confidence.reasons}
                            warnings={detail.warnings}
                        />
                        <DuplicatesCard duplicates={detail.duplicates} queue={queue} />
                        <HistoryCard reviews={detail.reviews} />
                    </div>
                    <DocumentTabs
                        pdfSrc={`/api/review/decisions/${detail.extraction_id}/file`}
                        pdf={detail.pdf}
                        text={
                            <TextPanel
                                fullText={fields.fullText}
                                editorialSummary={fields.editorialSummary}
                            />
                        }
                    />
                </div>
                <ActionBar />
            </main>
        </ReviewProvider>
    );
}
