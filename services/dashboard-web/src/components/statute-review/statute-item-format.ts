import { useFormatter, useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { useArticleLabel } from "./use-article-label";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

export type StatuteItem = components["schemas"]["StatuteReviewListItem"];

/**
 * How an article of the queue reads on screen. The table and the card list are two views of the
 * same data and both format it through this, so a label or a date cannot differ between them.
 */
export function useStatuteItemFormat() {
    const t = useTranslations("review.statutes.item");
    const format = useFormatter();
    const labels = useEnumLabels();
    const article = useArticleLabel();
    const { date } = useDates();
    const { empty, separator } = useCommon();

    return {
        empty,
        separator,
        unknownReasonLabel: t("unknownReason"),
        band: labels.band,
        reason: labels.statuteReason,
        isKnownReason: labels.isKnownStatuteReason,
        reasonHelp: (): undefined => undefined,
        count: (value: number) => format.number(value, "integer"),
        title: (item: StatuteItem) => article.title(item.article_no, item.heading),
        counts: (item: StatuteItem) =>
            t("counts", { versions: item.version_count, gaps: item.gap_count }),
        snapshot: (item: StatuteItem) => date(item.latest_snapshot_date),
        status: (item: StatuteItem) => labels.statuteStatus(item.status),
    };
}

export type StatuteItemFormat = ReturnType<typeof useStatuteItemFormat>;
