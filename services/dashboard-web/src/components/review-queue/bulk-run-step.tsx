"use client";

import { Button, DialogActions } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { BulkState } from "@/lib/bulk-approve";
import { BulkCounters } from "./bulk-counters";
import { BulkStepHeading } from "./bulk-step-heading";

/** Stop waits for the call in flight; the dialog stays shut until the run has answered. */
export function BulkRunStep({
    state,
    stopping,
    onStop,
}: {
    state: BulkState;
    stopping: boolean;
    onStop: () => void;
}) {
    const t = useTranslations("review.bulk.run");
    return (
        <div className="grid gap-4">
            <BulkStepHeading>{t("heading")}</BulkStepHeading>
            <BulkCounters state={state} />
            <p role="status" className="text-sm text-ink-2">
                {stopping ? t("stopping") : t("running")}
            </p>
            <DialogActions>
                <Button type="button" variant="outline" onClick={onStop} disabled={stopping}>
                    {t("stop")}
                </Button>
            </DialogActions>
        </div>
    );
}
