"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import type { QueueParams } from "@/lib/queue-params";
import { BulkApproveDialog } from "./bulk-approve-dialog";
import type { BulkSample } from "./bulk-confirm-step";
import { useQueueNavigation } from "./queue-navigation";

type Props = {
    params: QueueParams;
    total: number;
    sample: BulkSample[];
    /** There is no list to confirm (it is loading or failed). */
    unavailable?: boolean;
};

/**
 * Only the high band is approved in bulk (the API refuses any other); elsewhere the button stays
 * and says why. `params` and `total` are those of the list on screen, and the button waits while
 * a filter change is still on its way, so the count the reviewer confirms is the one they see.
 */
export function BulkApproveButton({ params, total, sample, unavailable = false }: Props) {
    const t = useTranslations("review.bulk");
    const { isPending } = useQueueNavigation();
    const [open, setOpen] = useState(false);
    const button = useRef<HTMLButtonElement>(null);
    const hintId = useId();
    const allowed = params.band === "high";

    return (
        <>
            <span title={allowed ? undefined : t("bandOnly")} className="grid md:block">
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
                        {t("bandOnly")}
                    </span>
                )}
            </span>
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
