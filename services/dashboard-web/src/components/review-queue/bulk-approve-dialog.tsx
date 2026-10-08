"use client";

import { Dialog } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type { RefObject } from "react";

import type { QueueState } from "@/lib/queue-state";
import { useBulkApprove } from "@/lib/use-bulk-approve";
import { BulkConfirmStep, type BulkSample } from "./bulk-confirm-step";
import { BulkHaltedStep } from "./bulk-halted-step";
import { BulkReportStep } from "./bulk-report-step";
import { BulkRunStep } from "./bulk-run-step";

type Props = {
    onClose: () => void;
    returnFocusTo: RefObject<HTMLElement | null>;
    params: QueueState;
    /** The `total` of the list response for these filters: the number on screen. */
    total: number;
    /** The first records of that list. */
    sample: BulkSample[];
};

/**
 * Mounted only while open, so every opening starts at the confirmation. It cannot be closed while
 * a call is in flight; once the run has started, closing refreshes the queue and the counts.
 */
export function BulkApproveDialog({ onClose, returnFocusTo, params, total, sample }: Props) {
    const t = useTranslations("review.bulk");
    const router = useRouter();
    const run = useBulkApprove({ params, total });

    function close() {
        if (run.phase !== "confirm") router.refresh();
        onClose();
    }

    return (
        <Dialog
            open
            onClose={close}
            title={t("title")}
            dismissible={run.phase !== "running"}
            returnFocusTo={returnFocusTo}
            className="max-w-2xl"
        >
            {run.phase === "confirm" ? (
                <BulkConfirmStep
                    params={params}
                    total={total}
                    sample={sample}
                    onStart={run.start}
                    onCancel={close}
                />
            ) : null}
            {run.phase === "running" ? (
                <BulkRunStep state={run.state} stopping={run.stopping} onStop={run.stop} />
            ) : null}
            {run.phase === "halted" && run.end ? (
                <BulkHaltedStep
                    state={run.state}
                    end={run.end}
                    onRetry={run.retry}
                    onResume={run.resume}
                    onReport={run.showReport}
                />
            ) : null}
            {run.phase === "report" ? (
                <BulkReportStep state={run.state} end={run.end} params={params} onClose={close} />
            ) : null}
        </Dialog>
    );
}
