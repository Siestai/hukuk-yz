"use client";

import { Button } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { BulkEnd, BulkState } from "@/lib/bulk-approve";
import { detailHref, type QueueParams } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useErrorMessage } from "@/lib/use-error-message";
import { BulkCounters } from "./bulk-counters";

/** How many records of a list the report names; the rest is a count. */
const MAX_LISTED = 20;

/** A listed record: its id links to the detail screen, which keeps the queue filters. */
function RecordLink({
    id,
    params,
    children,
}: {
    id: string;
    params: QueueParams;
    children?: ReactNode;
}) {
    return (
        <li className="flex justify-between gap-4">
            <Link href={detailHref(id, params)} className="font-mono text-primary underline">
                {id}
            </Link>
            {children}
        </li>
    );
}

type Props = {
    state: BulkState;
    end: BulkEnd | null;
    params: QueueParams;
    onClose: () => void;
};

export function BulkReportStep({ state, end, params, onClose }: Props) {
    const t = useTranslations("review.bulk.report");
    const labels = useEnumLabels();
    const errorMessage = useErrorMessage();
    const unprocessed = state.total - state.done;

    const more = (count: number) =>
        count > MAX_LISTED ? (
            <li className="text-ink-2">{t("more", { count: count - MAX_LISTED })}</li>
        ) : null;

    return (
        <div className="grid gap-4">
            <BulkCounters state={state} />
            {end?.kind === "stopped" ? (
                <p role="status" className="text-sm text-ink-2">
                    {t("stopped", { count: unprocessed })}
                </p>
            ) : null}
            {end?.kind === "failed" ? (
                <p role="alert" className="text-sm text-destructive">
                    {errorMessage(end.code, end.params)} {t("unprocessed", { count: unprocessed })}
                </p>
            ) : null}
            {state.conflicts.length > 0 ? (
                <section className="grid gap-1">
                    <h3 className="text-sm font-medium text-ink">{t("conflicts")}</h3>
                    <p className="text-sm text-ink-2">{t("conflictsHint")}</p>
                    <ul className="grid gap-1 text-sm">
                        {state.conflicts.slice(0, MAX_LISTED).map((id) => (
                            <RecordLink key={id} id={id} params={params} />
                        ))}
                        {more(state.conflicts.length)}
                    </ul>
                </section>
            ) : null}
            {state.failed.length > 0 ? (
                <section className="grid gap-1">
                    <h3 className="text-sm font-medium text-ink">{t("failures")}</h3>
                    <ul className="grid gap-1 text-sm">
                        {state.failed.slice(0, MAX_LISTED).map((failure) => (
                            <RecordLink key={failure.id} id={failure.id} params={params}>
                                <span className="text-ink-2">
                                    {labels.bulkFailure(failure.reason)}
                                </span>
                            </RecordLink>
                        ))}
                        {more(state.failed.length)}
                    </ul>
                </section>
            ) : null}
            <div className="flex justify-end">
                <Button type="button" onClick={onClose}>
                    {t("close")}
                </Button>
            </div>
        </div>
    );
}
