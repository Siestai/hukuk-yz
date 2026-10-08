import { useTranslations } from "next-intl";

import type { AsOfResult, TimelineEntry } from "@/lib/statute-as-of";
import { useDates } from "@/lib/use-dates";
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
            {result.stale ? (
                <p className="text-ink-2">{t("stale", { date: date(latestSnapshotDate) })}</p>
            ) : null}
        </div>
    );
}
