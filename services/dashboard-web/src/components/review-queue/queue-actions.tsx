"use client";

import { Button, Select } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId } from "react";

import { SORTS, type Sort } from "@/lib/queue-params";
import { useQueueNavigation } from "./queue-navigation";

export function QueueActions() {
    const t = useTranslations("review.queue");
    const { params, navigate } = useQueueNavigation();
    const hintId = useId();

    return (
        <div className="flex items-center gap-3">
            <Select
                aria-label={t("sort.label")}
                className="w-48"
                value={params.sort}
                onChange={(event) => navigate({ sort: event.target.value as Sort })}
            >
                {SORTS.map((sort) => (
                    <option key={sort} value={sort}>
                        {t(`sort.${sort}`)}
                    </option>
                ))}
            </Select>
            <span title={t("bulkApproveSoon")}>
                <Button disabled aria-describedby={hintId}>
                    {t("bulkApprove")}
                </Button>
                <span id={hintId} className="sr-only">
                    {t("bulkApproveSoon")}
                </span>
            </span>
        </div>
    );
}
