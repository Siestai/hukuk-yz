"use client";

import { Button, DialogActions } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { BulkEnd, BulkState } from "@/lib/bulk-approve";
import { detailHref, type QueueParams } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useErrorMessage } from "@/lib/use-error-message";
import { BulkCounters } from "./bulk-counters";
import { BulkStepHeading } from "./bulk-step-heading";

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
        <li className="flex flex-wrap justify-between gap-x-4 gap-y-1">
            <Link
                href={detailHref(id, params)}
                className="font-mono wrap-anywhere text-primary underline"
            >
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
    // After a changed queue the API's new count is the one left to do.
    const unprocessed = end?.kind === "count_changed" ? end.total : state.total - state.done;
    const heading =
        end?.kind === "finished" ? "finished" : end?.kind === "failed" ? "failed" : "stopped";

    const more = (count: number) =>
        count > MAX_LISTED ? (
            <li className="text-ink-2">{t("more", { count: count - MAX_LISTED })}</li>
        ) : null;

    return (
        <div className="grid gap-4">
            <BulkStepHeading>{t(`heading.${heading}`)}</BulkStepHeading>
            <BulkCounters state={state} />
            {end?.kind === "stopped" || end?.kind === "count_changed" ? (
                <p role="status" className="text-sm text-ink-2">
                    {end.kind === "stopped"
                        ? t("stopped", { count: unprocessed })
                        : t("countChanged", { count: unprocessed })}
                </p>
            ) : null}
            {state.lost ? (
                <p role="status" className="text-sm text-ink-2">
                    {t("undercounted")}
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
            <DialogActions>
                <Button type="button" onClick={onClose}>
                    {t("close")}
                </Button>
            </DialogActions>
        </div>
    );
}
