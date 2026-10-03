"use client";

import { Progress } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { BulkState } from "@/lib/bulk-approve";

/** Progress in records (`done / total`) and the three counters, as they stand. */
export function BulkCounters({ state }: { state: BulkState }) {
    const t = useTranslations("review.bulk.run");
    const counters = [
        ["published", state.published],
        ["conflicts", state.conflicts.length],
        ["failed", state.failed.length],
    ] as const;
    return (
        <div className="grid gap-3">
            <Progress aria-label={t("label")} value={state.done} max={state.total} />
            <div aria-live="polite" className="grid gap-3">
                <p className="text-sm text-ink">
                    {t("progress", { done: state.done, total: state.total })}
                </p>
                <dl className="grid grid-cols-3 gap-3 text-sm">
                    {counters.map(([key, count]) => (
                        <div key={key}>
                            <dt className="text-ink-2">{t(key)}</dt>
                            <dd className="text-lg font-semibold text-ink">
                                {t("count", { count })}
                            </dd>
                        </div>
                    ))}
                </dl>
            </div>
        </div>
    );
}
