"use client";

import { Badge, cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { TimelineGap } from "@/lib/statute-as-of";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { entryBox } from "./entry-box";
import { useLawLabel } from "./use-law-label";
import { useRange } from "./use-range";

export function GapEntry({ entry, matched }: { entry: TimelineGap; matched: boolean }) {
    const t = useTranslations("review.statutes.timeline");
    const labels = useEnumLabels();
    const range = useRange();
    const { date } = useDates();
    const lawLabel = useLawLabel();
    return (
        <div
            className={cn(
                entryBox,
                "border-dashed border-line-2 bg-surface-2",
                matched && "ring-2 ring-primary",
            )}
        >
            <span className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-ink">{range(entry.from, entry.to)}</span>
                <Badge variant="medium">{t("gap")}</Badge>
                {matched ? <Badge>{t("queried")}</Badge> : null}
            </span>
            <p className="font-medium text-ink">{t("gapNoText")}</p>
            <p className="text-xs text-ink-2">{labels.statuteWarning(entry.reason)}</p>
            {entry.known_amendments.length > 0 ? (
                <div className="grid gap-1">
                    <p className="text-xs font-medium text-ink-2">{t("knownAmendments")}</p>
                    <ul className="grid gap-1 text-xs text-ink-2">
                        {entry.known_amendments.map((amendment) => (
                            <li
                                key={`${amendment.law}-${amendment.date}-${amendment.kind}-${amendment.scope}`}
                            >
                                {amendment.scope
                                    ? t("amendmentScoped", {
                                          law: lawLabel(amendment.law),
                                          date: date(amendment.date),
                                          kind: labels.amendmentKind(amendment.kind),
                                          scope: amendment.scope,
                                      })
                                    : t("amendment", {
                                          law: lawLabel(amendment.law),
                                          date: date(amendment.date),
                                          kind: labels.amendmentKind(amendment.kind),
                                      })}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </div>
    );
}
