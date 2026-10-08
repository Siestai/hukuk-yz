"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import { HelpTip } from "@/components/help-tip";
import { isStatuteState, type QueueState } from "@/lib/queue-state";
import { BulkApproveDialog } from "./bulk-approve-dialog";
import type { BulkSample } from "./bulk-confirm-step";
import { useQueueNavigation } from "./queue-navigation";

type Props = {
    params: QueueState;
    total: number;
    sample: BulkSample[];
    /** There is no list to confirm (it is loading or failed). */
    unavailable?: boolean;
};

/**
 * Only the high band is approved in bulk (the API refuses any other), and the statute queue not
 * under a search; elsewhere the button stays and says why. `params` and `total` are those of the list on screen, and the button waits while
 * a filter change is still on its way, so the count the reviewer confirms is the one they see.
 */
export function BulkApproveButton({ params, total, sample, unavailable = false }: Props) {
    const t = useTranslations("review.bulk");
    const { isPending } = useQueueNavigation();
    const [open, setOpen] = useState(false);
    const button = useRef<HTMLButtonElement>(null);
    const hintId = useId();
    // The statute bulk scope is statute and band only: a search would confirm more than it lists.
    const searching = isStatuteState(params) && Boolean(params.q);
    const allowed = params.band === "high" && !searching;
    const hint = searching ? t("searchOnly") : t("bandOnly");

    return (
        <>
            <div className="flex items-center gap-2">
                <span
                    title={allowed ? undefined : hint}
                    className="grid flex-1 md:block md:flex-none"
                >
                    <Button
                        ref={button}
                        disabled={!allowed || unavailable || isPending}
                        aria-describedby={allowed ? undefined : hintId}
                        onClick={() => setOpen(true)}
                    >
                        {t("open")}
                    </Button>
                    {allowed ? null : (
                        <span id={hintId} className="sr-only">
                            {hint}
                        </span>
                    )}
                </span>
                <HelpTip name="bulk" topic={t("open")} />
            </div>
            {open ? (
                <BulkApproveDialog
                    onClose={() => setOpen(false)}
                    returnFocusTo={button}
                    params={params}
                    total={total}
                    sample={sample}
                />
            ) : null}
        </>
    );
}
