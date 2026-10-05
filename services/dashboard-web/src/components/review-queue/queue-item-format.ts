import { useFormatter, useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import type { QueueStatus } from "@/lib/queue-params";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

export type QueueItem = components["schemas"]["ReviewListItem"];

/** What a record's badge says: waiting, approved, approved after the reviewer's corrections, or rejected. */
export type ItemStatus = "pending" | "approved" | "edited" | "rejected";

export function itemStatus(item: QueueItem): ItemStatus {
    if (item.source_status === "analyzed") return "pending";
    if (item.source_status === "rejected") return "rejected";
    return item.review_decision === "edit" ? "edited" : "approved";
}

/** The extra columns (and card lines) of a tab: the queue has none, the others show the review. */
export type Extra = "status" | "review" | "note";
export const EXTRAS: Record<QueueStatus, readonly Extra[]> = {
    pending: [],
    approved: ["status", "review"],
    rejected: ["review", "note"],
    all: ["status", "review", "note"],
};

/**
 * How a queue record reads on screen. The table and the card list are two views of the same data
 * and both format it through this, so a label or a date cannot differ between them.
 */
export function useQueueItemFormat() {
    const t = useTranslations("review.queue.table");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { date, dateTime } = useDates();
    const { empty, separator } = useCommon();

    return {
        empty,
        separator,
        duplicateLabel: t("duplicate"),
        unknownReasonLabel: t("unknownReason"),
        band: labels.band,
        court: labels.court,
        reason: labels.reason,
        reasonHelp: labels.reasonHelp,
        isKnownReason: labels.isKnownReason,
        score: (item: QueueItem) => format.number(item.score, "score"),
        count: (value: number) => format.number(value, "integer"),
        numbers: (item: QueueItem) =>
            [
                item.esas_no && t("esas", { value: item.esas_no }),
                item.karar_no && t("karar", { value: item.karar_no }),
            ]
                .filter(Boolean)
                .join(separator) || empty,
        date: (item: QueueItem) => date(item.decision_date),
        issue: (item: QueueItem) => item.journal_issue ?? empty,
        status: (item: QueueItem) => t(`statuses.${itemStatus(item)}`),
        reviewedAt: (item: QueueItem) => (item.reviewed_at ? dateTime(item.reviewed_at) : empty),
        reviewedOn: (item: QueueItem) =>
            item.reviewed_at ? t("reviewedOn", { date: dateTime(item.reviewed_at) }) : empty,
        reviewer: (item: QueueItem) =>
            item.reviewed_at ? (item.reviewer_name ?? t("unknownReviewer")) : empty,
        note: (item: QueueItem) => item.note ?? empty,
        noteLine: (item: QueueItem) => (item.note ? t("noteValue", { note: item.note }) : null),
    };
}

export type QueueItemFormat = ReturnType<typeof useQueueItemFormat>;
