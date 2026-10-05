"use client";

import { Select } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { SORTS, type Sort } from "@/lib/queue-params";
import { useQueueNavigation } from "./queue-navigation";

/** The sort control, and the bulk approve button the page puts beside it. */
export function QueueActions({ children }: { children?: ReactNode }) {
    const t = useTranslations("review.queue");
    const { params, navigate } = useQueueNavigation();

    return (
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <Select
                aria-label={t("sort.label")}
                className="md:w-48"
                value={params.sort}
                onChange={(event) => navigate({ sort: event.target.value as Sort })}
            >
                {SORTS.map((sort) => (
                    <option key={sort} value={sort}>
                        {t(`sort.${sort}`)}
                    </option>
                ))}
            </Select>
            {children}
        </div>
    );
}
