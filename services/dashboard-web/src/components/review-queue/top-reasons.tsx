"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { useEnumLabels } from "@/lib/use-enum-labels";
import { useQueueNavigation } from "./use-queue-navigation";

const SHOWN = 5;

export function TopReasons({ reasons }: { reasons: { reason: string; count: number }[] }) {
    const t = useTranslations("review.queue.summary");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { params, navigate } = useQueueNavigation();

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
                        {reasons.slice(0, SHOWN).map(({ reason, count }) => (
                            <li key={reason}>
                                <button
                                    type="button"
                                    aria-pressed={params.reason === reason}
                                    onClick={() =>
                                        navigate({
                                            reason: params.reason === reason ? undefined : reason,
                                        })
                                    }
                                    className="flex w-full items-center justify-between gap-3 rounded-md px-2 py-1 text-left text-sm text-ink hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-ring aria-pressed:bg-primary-soft"
                                >
                                    {labels.reason(reason)}
                                    <span className="font-mono text-ink-2">
                                        {format.number(count, "integer")}
                                    </span>
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </CardContent>
        </Card>
    );
}
