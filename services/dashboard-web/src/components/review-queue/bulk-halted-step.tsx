"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { BulkEnd, BulkState } from "@/lib/bulk-approve";
import { useErrorMessage } from "@/lib/use-error-message";
import { BulkConfirmCheck } from "./bulk-confirm-check";
import { BulkCounters } from "./bulk-counters";

type Props = {
    state: BulkState;
    end: BulkEnd;
    onRetry: () => void;
    onResume: (expected: number) => void;
    onReport: () => void;
};

/** A halt the user can act on: the queue changed (confirm the new count) or the API was out of reach (repeat). */
export function BulkHaltedStep({ state, end, onRetry, onResume, onReport }: Props) {
    const t = useTranslations("review.bulk.halted");
    const errorMessage = useErrorMessage();
    const [checked, setChecked] = useState(false);

    return (
        <div className="grid gap-4">
            <BulkCounters state={state} />
            {end.kind === "count_changed" ? (
                <>
                    <p role="alert" className="text-sm font-medium text-ink">
                        {t("countChanged", { total: end.total })}
                    </p>
                    {end.total > 0 ? (
                        <BulkConfirmCheck
                            count={end.total}
                            checked={checked}
                            onChange={setChecked}
                        />
                    ) : null}
                </>
            ) : (
                <p role="alert" className="text-sm text-destructive">
                    {errorMessage(end.kind === "failed" ? end.code : undefined)}
                </p>
            )}
            <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={onReport}>
                    {t("report")}
                </Button>
                {end.kind === "count_changed" ? (
                    <Button
                        type="button"
                        disabled={end.total === 0 || !checked}
                        onClick={() => onResume(end.total)}
                    >
                        {t("resume", { total: end.total })}
                    </Button>
                ) : (
                    <Button type="button" onClick={onRetry}>
                        {t("retry")}
                    </Button>
                )}
            </div>
        </div>
    );
}
