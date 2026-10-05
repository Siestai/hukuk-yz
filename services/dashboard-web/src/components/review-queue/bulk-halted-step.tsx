"use client";

import { Button, DialogActions } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { BulkEnd, BulkState } from "@/lib/bulk-approve";
import { useErrorMessage } from "@/lib/use-error-message";
import { BulkConfirmCheck } from "./bulk-confirm-check";
import { BulkCounters } from "./bulk-counters";
import { BulkStepHeading } from "./bulk-step-heading";

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
            <BulkStepHeading>{t("heading")}</BulkStepHeading>
            <BulkCounters state={state} />
            {end.kind === "count_changed" ? (
                <>
                    <p role="alert" className="text-sm font-medium text-ink">
                        {state.lost ? t("mayHaveApplied") : t("countChanged", { total: end.total })}
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
                <>
                    <p role="alert" className="text-sm text-destructive">
                        {errorMessage(end.kind === "failed" ? end.code : undefined)}
                    </p>
                    <p className="text-sm text-ink-2">{t("mayHaveApplied")}</p>
                </>
            )}
            <DialogActions>
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
            </DialogActions>
        </div>
    );
}
