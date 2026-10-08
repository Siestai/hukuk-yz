"use client";

import { Badge, cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { TimelineVersion } from "@/lib/statute-as-of";
import { parseAmendingRef } from "@/lib/statute-timeline";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { entryBox } from "./entry-box";
import { useLawLabel } from "./use-law-label";
import { useRange } from "./use-range";

export function VersionEntry({
    entry,
    selected,
    matched,
    onSelect,
}: {
    entry: TimelineVersion;
    selected: boolean;
    matched: boolean;
    onSelect: () => void;
}) {
    const t = useTranslations("review.statutes.timeline");
    const labels = useEnumLabels();
    const range = useRange();
    const { date } = useDates();
    const lawLabel = useLawLabel();
    const laws = parseAmendingRef(entry.amending_ref).map((ref) => lawLabel(ref.law));

    return (
        <button
            type="button"
            aria-pressed={selected}
            onClick={onSelect}
            className={cn(
                entryBox,
                "w-full text-left pointer-coarse:min-h-11 hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring",
                selected ? "border-primary bg-primary-soft" : "border-border bg-surface",
                matched && "ring-2 ring-primary",
            )}
        >
            <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-ink">
                    {range(entry.valid_from, entry.valid_to)}
                </span>
                <Badge variant="outline">{labels.changeKind(entry.change_kind)}</Badge>
                {entry.confidence && entry.confidence !== "high" ? (
                    <Badge variant={entry.confidence}>{labels.band(entry.confidence)}</Badge>
                ) : null}
                {matched ? <Badge>{t("queried")}</Badge> : null}
            </span>
            {laws.length > 0 ? (
                <span className="text-xs text-ink-2">
                    {t("amendedBy", { laws: laws.join(", "), date: date(entry.valid_from) })}
                </span>
            ) : null}
        </button>
    );
}
