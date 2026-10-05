"use client";

import { Select } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { HelpTip } from "@/components/help-tip";
import { sortsFor, statusOf, type Sort } from "@/lib/queue-params";
import { useQueueNavigation } from "./queue-navigation";

/** The sort control, and the bulk approve button the page puts beside it. */
export function QueueActions({ children }: { children?: ReactNode }) {
    const t = useTranslations("review.queue");
    const { params, navigate } = useQueueNavigation();

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex items-center gap-2">
                <Select
                    aria-label={t("sort.label")}
                    className="min-w-0 flex-1 md:w-48 md:flex-none"
                    value={params.sort}
                    onChange={(event) => navigate({ sort: event.target.value as Sort })}
                >
                    {sortsFor(statusOf(params)).map((sort) => (
                        <option key={sort} value={sort}>
                            {t(`sort.${sort}`)}
                        </option>
                    ))}
                </Select>
                <HelpTip name="sort" topic={t("sort.label")} />
            </div>
            {children}
        </div>
    );
}
