import { useTranslations } from "next-intl";

import type { AsOfResult, TimelineEntry } from "@/lib/statute-as-of";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useRange } from "./use-range";

/** What the answer says, by status: the interval it came from or why there is no text. */
export function DateQueryAnswer({
    result,
    timeline,
    latestSnapshotDate,
}: {
    result: AsOfResult;
    timeline: TimelineEntry[];
    latestSnapshotDate: string;
}) {
    const t = useTranslations("review.statutes.dateQuery");
    const range = useRange();
    const { date } = useDates();
    const labels = useEnumLabels();
    const entry = result.index === null ? undefined : timeline[result.index];
    const interval =
        entry?.kind === "version"
            ? range(entry.valid_from, entry.valid_to)
            : entry?.kind === "gap"
              ? range(entry.from, entry.to)
              : "";

    return (
        <div className="grid gap-1 text-sm">
            <p className="font-medium text-ink">
                {result.status === "found"
                    ? t("found", { range: interval })
                    : result.status === "gap"
                      ? t("gap", { range: interval })
                      : result.reason === "repealed"
                        ? t("repealed", { range: interval })
                        : t("notInForce")}
            </p>
            {result.status === "found" && result.confidence ? (
                <p className="text-ink-2">
                    {t("confidence", { band: labels.band(result.confidence) })}
                </p>
            ) : null}
            {result.status === "found" && result.confidence === "low" ? (
                <p className="font-medium text-low">{t("lowConfidence")}</p>
            ) : null}
            {result.stale ? (
                <p className="text-ink-2">{t("stale", { date: date(latestSnapshotDate) })}</p>
            ) : null}
        </div>
    );
}
