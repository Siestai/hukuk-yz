"use client";

import { Label, Select } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useId } from "react";

import { HelpTip } from "@/components/help-tip";
import { FilterShell } from "@/components/review-queue/filter-shell";
import { useQueueNavigation } from "@/components/review-queue/queue-navigation";
import { SearchBox } from "@/components/review-queue/search-box";
import { BANDS, type Band } from "@/lib/queue-params";
import {
    activeStatuteFilterCount,
    statuteListHref,
    type StatuteQueueParams,
} from "@/lib/statute-queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";

/** Band and search; the statute and the status are tabs. */
export function StatuteFilters() {
    const t = useTranslations("review");
    const labels = useEnumLabels();
    const { params, navigate } = useQueueNavigation<StatuteQueueParams>();
    const ids = { band: useId(), q: useId() };
    const active = activeStatuteFilterCount(params);

    return (
        <FilterShell active={active}>
            <div className="grid gap-1.5 md:w-40">
                <div className="flex items-center gap-1.5">
                    <Label htmlFor={ids.band}>{t("queue.filters.band")}</Label>
                    <HelpTip name="filterBand" scope="statutes" topic={t("queue.filters.band")} />
                </div>
                <Select
                    id={ids.band}
                    value={params.band ?? ""}
                    onChange={(event) =>
                        navigate({ band: (event.target.value || undefined) as Band })
                    }
                >
                    <option value="">{t("queue.filters.allBands")}</option>
                    {BANDS.map((band) => (
                        <option key={band} value={band}>
                            {labels.band(band)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid gap-1.5 md:min-w-56 md:flex-1">
                <div className="flex items-center gap-1.5">
                    <Label htmlFor={ids.q}>{t("statutes.filters.search")}</Label>
                    <HelpTip
                        name="filterSearch"
                        scope="statutes"
                        topic={t("statutes.filters.search")}
                    />
                </div>
                <SearchBox id={ids.q} />
            </div>
            {active > 0 ? (
                <div className="flex items-center gap-2">
                    <Link
                        href={statuteListHref({
                            kind: "statute",
                            statute: params.statute,
                            status: params.status,
                            page: 1,
                        })}
                        className="inline-flex items-center py-2 text-sm font-medium text-primary underline pointer-coarse:min-h-11"
                    >
                        {t("queue.filters.clear")}
                    </Link>
                    <HelpTip name="filterClear" scope="statutes" topic={t("queue.filters.clear")} />
                </div>
            ) : null}
        </FilterShell>
    );
}
