"use client";

import { Input, Label, Select } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useId } from "react";

import {
    BANDS,
    COURTS,
    hasFilters,
    MAX_JOURNAL_ISSUE,
    parseJournalIssue,
    queueHref,
    UNKNOWN_COURT,
    type Band,
} from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { SearchBox } from "./search-box";
import { useQueueNavigation } from "./queue-navigation";

export function QueueFilters({ courts }: { courts: string[] }) {
    const t = useTranslations("review.queue.filters");
    const labels = useEnumLabels();
    const { params, navigate } = useQueueNavigation();
    const ids = { band: useId(), court: useId(), reason: useId(), issue: useId(), q: useId() };

    // The API's empty court is `unknown` in the URL. A court chosen in the URL stays selectable;
    // a court this UI does not know is ignored.
    const present = new Set([
        ...courts.map((court) => (court === "" ? UNKNOWN_COURT : court)),
        ...(params.court ? [params.court] : []),
    ]);
    const courtOptions = [...COURTS, UNKNOWN_COURT].filter((court) => present.has(court));
    const reasonOptions = [...labels.reasonCodes].sort((a, b) =>
        labels.reason(a).localeCompare(labels.reason(b), "tr"),
    );
    const commitIssue = (value: string) => {
        if (value.trim() === "") return navigate({ journalIssue: undefined });
        const issue = parseJournalIssue(value);
        if (issue !== undefined) navigate({ journalIssue: issue });
    };

    return (
        <section aria-label={t("label")} className="flex flex-wrap items-end gap-4">
            <div className="grid w-40 gap-1.5">
                <Label htmlFor={ids.band}>{t("band")}</Label>
                <Select
                    id={ids.band}
                    value={params.band ?? ""}
                    onChange={(event) =>
                        navigate({ band: (event.target.value || undefined) as Band })
                    }
                >
                    <option value="">{t("allBands")}</option>
                    {BANDS.map((band) => (
                        <option key={band} value={band}>
                            {labels.band(band)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid w-48 gap-1.5">
                <Label htmlFor={ids.court}>{t("court")}</Label>
                <Select
                    id={ids.court}
                    value={params.court ?? ""}
                    onChange={(event) => navigate({ court: event.target.value || undefined })}
                >
                    <option value="">{t("allCourts")}</option>
                    {courtOptions.map((court) => (
                        <option key={court} value={court}>
                            {labels.court(court)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid w-64 gap-1.5">
                <Label htmlFor={ids.reason}>{t("reason")}</Label>
                <Select
                    id={ids.reason}
                    value={params.reason ?? ""}
                    onChange={(event) => navigate({ reason: event.target.value || undefined })}
                >
                    <option value="">{t("allReasons")}</option>
                    {reasonOptions.map((reason) => (
                        <option key={reason} value={reason}>
                            {labels.reason(reason)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid w-32 gap-1.5">
                <Label htmlFor={ids.issue}>{t("journalIssue")}</Label>
                <Input
                    key={params.journalIssue ?? ""}
                    id={ids.issue}
                    type="number"
                    min={1}
                    max={MAX_JOURNAL_ISSUE}
                    defaultValue={params.journalIssue ?? ""}
                    onBlur={(event) => {
                        if (event.target.value.trim() !== String(params.journalIssue ?? "")) {
                            commitIssue(event.target.value);
                        }
                    }}
                    onKeyDown={(event) => {
                        if (event.key === "Enter") commitIssue(event.currentTarget.value);
                    }}
                />
            </div>
            <div className="grid min-w-56 flex-1 gap-1.5">
                <Label htmlFor={ids.q}>{t("search")}</Label>
                <SearchBox id={ids.q} />
            </div>
            {hasFilters(params) ? (
                <Link
                    href={queueHref({ sort: params.sort, page: 1 })}
                    className="py-2 text-sm font-medium text-primary underline"
                >
                    {t("clear")}
                </Link>
            ) : null}
        </section>
    );
}
