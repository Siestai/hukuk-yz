"use client";

import { useTranslations } from "next-intl";

import type { TimelineEntry } from "@/lib/statute-as-of";
import { GapEntry } from "./gap-entry";
import { VersionEntry } from "./version-entry";

/**
 * The timeline of an article, oldest first, vertical at every width. A version is a button that
 * selects it; a gap states that there is no text and lists the amendments known to fall in it,
 * and never shows any text.
 */
export function TimelineList({
    timeline,
    selected,
    matched,
    onSelect,
}: {
    timeline: TimelineEntry[];
    selected: number | null;
    /** The entry the queried date falls in. */
    matched: number | null;
    onSelect: (index: number) => void;
}) {
    const t = useTranslations("review.statutes.timeline");
    return (
        <ol aria-label={t("label")} className="grid gap-3 border-l-2 border-line pl-3">
            {timeline.map((entry, index) => (
                <li
                    key={`${entry.kind}-${entry.kind === "version" ? entry.valid_from : (entry.from ?? "start")}`}
                >
                    {entry.kind === "version" ? (
                        <VersionEntry
                            entry={entry}
                            selected={selected === index}
                            matched={matched === index}
                            onSelect={() => onSelect(index)}
                        />
                    ) : (
                        <GapEntry entry={entry} matched={matched === index} />
                    )}
                </li>
            ))}
        </ol>
    );
}
