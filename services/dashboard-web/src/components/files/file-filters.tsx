"use client";

import { Button, Input, Label, Select } from "@hukuk/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useEffectEvent, useId, useRef, useState } from "react";

import { FilterShell } from "@/components/review-queue/filter-shell";
import {
    activeFileFilters,
    changeFileParams,
    DOC_TYPES,
    fileListHref,
    parseFileParams,
    serializeFileParams,
    SCAN_STATUSES,
    type FileListParams,
} from "@/lib/files";
import { useEnumLabels } from "@/lib/use-enum-labels";

const SEARCH_DEBOUNCE_MS = 300;

/** Type, scan status and search of the file list; the state lives in the URL. */
export function FileFilters() {
    const t = useTranslations("files.filters");
    const labels = useEnumLabels();
    const router = useRouter();
    const params = parseFileParams(useSearchParams());
    const ids = { type: useId(), scan: useId(), q: useId() };
    const [text, setText] = useState(params.q ?? "");
    const active = activeFileFilters(params);

    // Changes build on the latest change, not on the URL the router has caught up with, so two
    // quick changes both land. A URL we pushed ourselves keeps `latest` ahead of it; any other
    // URL (back button, a link) is the new truth.
    const key = serializeFileParams(params).toString();
    const latest = useRef(params);
    const inFlight = useRef<string[]>([]);
    useEffect(() => {
        const at = inFlight.current.indexOf(key);
        if (at >= 0) {
            inFlight.current = inFlight.current.slice(at + 1);
        } else {
            inFlight.current = [];
            latest.current = parseFileParams(new URLSearchParams(key));
        }
    }, [key]);

    function navigate(next: FileListParams, mode: "push" | "replace" = "push") {
        latest.current = next;
        inFlight.current.push(serializeFileParams(next).toString());
        router[mode](fileListHref(next));
    }
    const go = (change: Partial<FileListParams>, mode?: "push" | "replace") =>
        navigate(changeFileParams(latest.current, change), mode);

    // Typing updates the URL after a pause; Enter does it at once.
    const typed = text.trim();
    const sendAfterPause = useEffectEvent((value: string) =>
        go({ q: value || undefined }, "replace"),
    );
    useEffect(() => {
        if (typed === (latest.current.q ?? "")) return;
        const timer = setTimeout(() => sendAfterPause(typed), SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [typed, key]);

    return (
        <FilterShell active={active}>
            <div className="grid gap-1.5 md:w-56">
                <Label htmlFor={ids.type}>{t("docType")}</Label>
                <Select
                    id={ids.type}
                    value={params.docType ?? ""}
                    onChange={(event) =>
                        go({
                            docType: (event.target.value || undefined) as FileListParams["docType"],
                        })
                    }
                >
                    <option value="">{t("allTypes")}</option>
                    {DOC_TYPES.map((type) => (
                        <option key={type} value={type}>
                            {labels.docType(type)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid gap-1.5 md:w-48">
                <Label htmlFor={ids.scan}>{t("scan")}</Label>
                <Select
                    id={ids.scan}
                    value={params.scan ?? ""}
                    onChange={(event) =>
                        go({ scan: (event.target.value || undefined) as FileListParams["scan"] })
                    }
                >
                    <option value="">{t("allScans")}</option>
                    {SCAN_STATUSES.map((status) => (
                        <option key={status} value={status}>
                            {labels.scanStatus(status)}
                        </option>
                    ))}
                </Select>
            </div>
            <div className="grid gap-1.5 md:min-w-56 md:flex-1">
                <Label htmlFor={ids.q}>{t("search")}</Label>
                <form
                    role="search"
                    onSubmit={(event) => {
                        event.preventDefault();
                        go({ q: typed || undefined });
                    }}
                >
                    <Input
                        id={ids.q}
                        type="search"
                        value={text}
                        maxLength={100}
                        placeholder={t("searchPlaceholder")}
                        onChange={(event) => setText(event.target.value)}
                    />
                </form>
            </div>
            {active > 0 ? (
                <Button
                    type="button"
                    variant="ghost"
                    className="text-primary underline"
                    onClick={() => {
                        setText("");
                        navigate({ review: params.review });
                    }}
                >
                    {t("clear")}
                </Button>
            ) : null}
        </FilterShell>
    );
}
