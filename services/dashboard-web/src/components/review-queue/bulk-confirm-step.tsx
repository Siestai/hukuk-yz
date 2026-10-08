"use client";

import { Badge, Button, DialogActions } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { isStatuteState, type QueueState } from "@/lib/queue-state";
import { useCommon } from "@/lib/use-common";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { BulkConfirmCheck } from "./bulk-confirm-check";

/** A record shown as an example: decisions by their numbers, articles by a `note` line. */
export type BulkSample = {
    id: string;
    title: string;
    esasNo: string;
    kararNo: string;
    note?: string;
};

type Props = {
    params: QueueState;
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

    const statute = isStatuteState(params);
    const filters = [
        t("filters.band", { value: labels.band("high") }),
        statute ? t("filters.statute", { value: params.statute }) : null,
        !statute && params.court ? t("filters.court", { value: labels.court(params.court) }) : null,
        !statute && params.reason
            ? t("filters.reason", { value: labels.reason(params.reason) })
            : null,
        !statute && params.journalIssue ? t("filters.issue", { value: params.journalIssue }) : null,
        !statute && params.q ? t("filters.q", { value: params.q }) : null,
    ].filter((filter) => filter !== null);
    const numbers = (item: BulkSample) =>
        item.note ??
        ([
            item.esasNo && t("esas", { value: item.esasNo }),
            item.kararNo && t("karar", { value: item.kararNo }),
        ]
            .filter(Boolean)
            .join(separator) ||
            empty);

    return (
        <div className="grid gap-4">
            {total === 0 ? (
                <p className="text-sm text-ink-2">{t("none")}</p>
            ) : (
                <>
                    <p className="text-3xl font-semibold text-ink">
                        {statute ? t("countStatute", { total }) : t("count", { total })}
                    </p>
                    <p className="text-sm text-ink-2">{statute ? t("introStatute") : t("intro")}</p>
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
                            <li
                                key={item.id}
                                className="flex flex-col gap-0.5 md:flex-row md:justify-between md:gap-4"
                            >
                                <span className="min-w-0 wrap-anywhere text-ink">{item.title}</span>
                                <span className="shrink-0 text-ink-2">{numbers(item)}</span>
                            </li>
                        ))}
                    </ul>
                </section>
            ) : null}
            {total > 0 ? (
                <>
                    <p className="text-sm text-ink-2">
                        {statute ? t("unverifiedStatute") : t("unverified")}
                    </p>
                    <BulkConfirmCheck count={total} checked={checked} onChange={setChecked} />
                </>
            ) : null}
            <DialogActions>
                <Button type="button" variant="outline" onClick={onCancel}>
                    {t("cancel")}
                </Button>
                <Button type="button" onClick={onStart} disabled={total === 0 || !checked}>
                    {t("start")}
                </Button>
            </DialogActions>
        </div>
    );
}
