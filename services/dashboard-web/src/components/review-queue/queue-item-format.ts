import { useFormatter, useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

export type QueueItem = components["schemas"]["ReviewListItem"];

/**
 * How a queue record reads on screen. The table and the card list are two views of the same data
 * and both format it through this, so a label or a date cannot differ between them.
 */
export function useQueueItemFormat() {
    const t = useTranslations("review.queue.table");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { date } = useDates();
    const { empty, separator } = useCommon();

    return {
        empty,
        separator,
        duplicateLabel: t("duplicate"),
        unknownReasonLabel: t("unknownReason"),
        band: labels.band,
        court: labels.court,
        reason: labels.reason,
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
    };
}

export type QueueItemFormat = ReturnType<typeof useQueueItemFormat>;
