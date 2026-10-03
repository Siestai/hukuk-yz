"use client";

import { Badge, Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { QueueParams } from "@/lib/queue-params";
import { useCommon } from "@/lib/use-common";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { BulkConfirmCheck } from "./bulk-confirm-check";

export type BulkSample = { id: string; title: string; esasNo: string; kararNo: string };

type Props = {
    params: QueueParams;
    total: number;
    sample: BulkSample[];
    onStart: () => void;
    onCancel: () => void;
};

export function BulkConfirmStep({ params, total, sample, onStart, onCancel }: Props) {
    const t = useTranslations("review.bulk");
    const labels = useEnumLabels();
    const { empty, separator } = useCommon();
    const [checked, setChecked] = useState(false);

    const filters = [
        t("filters.band", { value: labels.band("high") }),
        params.court ? t("filters.court", { value: labels.court(params.court) }) : null,
        params.reason ? t("filters.reason", { value: labels.reason(params.reason) }) : null,
        params.journalIssue ? t("filters.issue", { value: params.journalIssue }) : null,
        params.q ? t("filters.q", { value: params.q }) : null,
    ].filter((filter) => filter !== null);
    const numbers = (item: BulkSample) =>
        [
            item.esasNo && t("esas", { value: item.esasNo }),
            item.kararNo && t("karar", { value: item.kararNo }),
        ]
            .filter(Boolean)
            .join(separator) || empty;

    return (
        <div className="grid gap-4">
            {total === 0 ? (
                <p className="text-sm text-ink-2">{t("none")}</p>
            ) : (
                <>
                    <p className="text-3xl font-semibold text-ink">{t("count", { total })}</p>
                    <p className="text-sm text-ink-2">{t("intro")}</p>
                </>
            )}
            <section aria-label={t("filtersLabel")}>
                <ul className="flex flex-wrap gap-2">
                    {filters.map((filter) => (
                        <li key={filter}>
                            <Badge variant="outline">{filter}</Badge>
                        </li>
                    ))}
                </ul>
            </section>
            {sample.length > 0 ? (
                <section className="grid gap-1">
                    <h3 className="text-sm font-medium text-ink">
                        {t("sampleTitle", { count: sample.length })}
                    </h3>
                    <ul className="grid gap-1 text-sm">
                        {sample.map((item) => (
                            <li key={item.id} className="flex justify-between gap-4">
                                <span className="text-ink">{item.title}</span>
                                <span className="shrink-0 text-ink-2">{numbers(item)}</span>
                            </li>
                        ))}
                    </ul>
                </section>
            ) : null}
            {total > 0 ? (
                <>
                    <p className="text-sm text-ink-2">{t("unverified")}</p>
                    <BulkConfirmCheck count={total} checked={checked} onChange={setChecked} />
                </>
            ) : null}
            <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={onCancel}>
                    {t("cancel")}
                </Button>
                <Button type="button" onClick={onStart} disabled={total === 0 || !checked}>
                    {t("start")}
                </Button>
            </div>
        </div>
    );
}
