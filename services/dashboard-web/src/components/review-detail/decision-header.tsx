import { Badge } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import { queueHref, type QueueParams } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";

type Props = {
    title: string;
    band: string;
    score: number;
    sourceStatus: string;
    queue: QueueParams;
};

/** The record's title, band and status. Why a record has no actions is told by `ReviewStatusStrip`. */
export function DecisionHeader({ title, band, score, sourceStatus, queue }: Props) {
    const t = useTranslations("review.detail");
    const format = useFormatter();
    const labels = useEnumLabels();
    return (
        <header className="grid gap-3">
            <Link
                href={queueHref(queue)}
                className="inline-flex w-fit items-center text-sm text-primary hover:underline pointer-coarse:min-h-11"
            >
                {t("back")}
            </Link>
            <h1 className="font-serif text-xl wrap-anywhere text-ink md:text-2xl">{title}</h1>
            <div className="flex flex-wrap items-center gap-2">
                <Badge variant={band === "high" || band === "medium" ? band : "low"}>
                    {labels.band(band)}
                </Badge>
                <span className="font-mono text-xs text-ink-2">
                    {format.number(score, "score")}
                </span>
                <Badge variant="outline">{labels.sourceStatus(sourceStatus)}</Badge>
            </div>
        </header>
    );
}
