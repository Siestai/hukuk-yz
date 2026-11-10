import { useFormatter, useTranslations } from "next-intl";

import type { JournalScanItem } from "@/lib/journal-scans";
import { readReason } from "@/lib/journal-scans";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

/**
 * How a scan reads on screen. The table, the cards and the detail page format through this, so a
 * label or a date cannot differ between them.
 */
export function useScanFormat() {
    const t = useTranslations("journalScans");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { dateTime } = useDates();
    const { empty, separator } = useCommon();

    return {
        empty,
        separator,
        startedAt: (scan: JournalScanItem) => dateTime(scan.started_at),
        finishedAt: (scan: JournalScanItem) =>
            scan.finished_at ? dateTime(scan.finished_at) : empty,
        trigger: (scan: JournalScanItem) => labels.journalTrigger(scan.trigger),
        count: (value: number) => format.number(value, "integer"),
        issues: (numbers: number[]) => (numbers.length > 0 ? numbers.join(", ") : empty),
        issueName: (no: number) => t("issueName", { no }),
        /** A reason with a plain-Turkish text where there is one; the raw code otherwise. */
        reason: (reason: string) => {
            const known = readReason(reason);
            if (!known) return reason;
            return known.key === "http"
                ? t("reasons.http", { status: known.status ?? 0 })
                : t(`reasons.${known.key}`);
        },
    };
}

export type ScanFormat = ReturnType<typeof useScanFormat>;
