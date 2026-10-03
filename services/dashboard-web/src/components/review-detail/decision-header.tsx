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

export function DecisionHeader({ title, band, score, sourceStatus, queue }: Props) {
    const t = useTranslations("review.detail");
    const format = useFormatter();
    const labels = useEnumLabels();
    return (
        <header className="grid gap-3">
            <Link href={queueHref(queue)} className="w-fit text-sm text-primary hover:underline">
                {t("back")}
            </Link>
            <h1 className="font-serif text-2xl text-ink">{title}</h1>
            <div className="flex flex-wrap items-center gap-2">
                <Badge variant={band === "high" || band === "medium" ? band : "low"}>
                    {labels.band(band)}
                </Badge>
                <span className="font-mono text-xs text-ink-2">
                    {format.number(score, "score")}
                </span>
                <Badge variant="outline">{labels.sourceStatus(sourceStatus)}</Badge>
            </div>
            {sourceStatus === "analyzed" ? null : (
                <p role="note" className="rounded-md bg-medium-soft p-3 text-sm text-medium">
                    {t("notQueued", { status: labels.sourceStatus(sourceStatus) })}
                </p>
            )}
        </header>
    );
}
