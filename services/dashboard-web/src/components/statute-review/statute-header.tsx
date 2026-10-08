import { Badge } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { stateHref } from "@/lib/queue-state";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useArticleLabel } from "./use-article-label";

type Props = {
    statuteNumber: string;
    statuteTitle: string;
    articleNo: string;
    heading: string | null;
    band: string;
    status: string;
    latestSnapshotDate: string;
    queue: StatuteQueueParams;
};

/** The article's title, band and status, and how recent the text is. */
export function StatuteHeader({
    statuteNumber,
    statuteTitle,
    articleNo,
    heading,
    band,
    status,
    latestSnapshotDate,
    queue,
}: Props) {
    const t = useTranslations("review.statutes.detail");
    const labels = useEnumLabels();
    const article = useArticleLabel();
    const { date } = useDates();
    return (
        <header className="grid gap-3">
            <Link
                href={stateHref(queue)}
                className="inline-flex w-fit items-center text-sm text-primary hover:underline pointer-coarse:min-h-11"
            >
                {t("back")}
            </Link>
            <h1 className="font-serif text-xl wrap-anywhere text-ink md:text-2xl">
                {t("heading", {
                    statute: statuteNumber,
                    article: article.title(articleNo, heading),
                })}
            </h1>
            <p className="text-sm wrap-anywhere text-ink-2">{statuteTitle}</p>
            <div className="flex flex-wrap items-center gap-2">
                <Badge variant={band === "high" || band === "medium" ? band : "low"}>
                    {labels.band(band)}
                </Badge>
                <Badge variant="outline">{labels.statuteStatus(status)}</Badge>
            </div>
            <p className="text-sm text-ink-2">
                {t("upToDate", { date: date(latestSnapshotDate) })}
            </p>
        </header>
    );
}
