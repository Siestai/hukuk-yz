import { Card, CardContent, CardHeader, CardTitle, cn } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import { changeQueueParams, queueHref, type QueueParams } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";

const SHOWN = 5;

export function TopReasons({
    reasons,
    params,
}: {
    reasons: { reason: string; count: number }[];
    params: QueueParams;
}) {
    const t = useTranslations("review.queue.summary");
    const format = useFormatter();
    const labels = useEnumLabels();

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("topReasons")}</CardTitle>
            </CardHeader>
            <CardContent>
                {reasons.length === 0 ? (
                    <p className="text-sm text-ink-3">{t("noReasons")}</p>
                ) : (
                    <ul className="grid gap-1">
                        {reasons.slice(0, SHOWN).map(({ reason, count }) => {
                            const active = params.reason === reason;
                            return (
                                <li key={reason}>
                                    <Link
                                        href={queueHref(
                                            changeQueueParams(params, {
                                                reason: active ? undefined : reason,
                                            }),
                                        )}
                                        aria-current={active ? "true" : undefined}
                                        className={cn(
                                            "flex w-full items-center justify-between gap-3 rounded-md px-2 py-1 text-left text-sm text-ink hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-ring",
                                            active && "bg-primary-soft",
                                        )}
                                    >
                                        {labels.reason(reason)}
                                        <span className="font-mono text-ink-2">
                                            {format.number(count, "integer")}
                                        </span>
                                    </Link>
                                </li>
                            );
                        })}
                    </ul>
                )}
            </CardContent>
        </Card>
    );
}
