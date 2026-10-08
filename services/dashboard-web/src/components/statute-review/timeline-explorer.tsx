"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { statuteAsOf, type TimelineEntry } from "@/lib/statute-as-of";
import { DateQuery } from "./date-query";
import { TimelineList } from "./timeline-list";
import { VersionPanel } from "./version-panel";

const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

function lastVersion(timeline: TimelineEntry[]): number | null {
    const index = timeline.findLastIndex((entry) => entry.kind === "version");
    return index < 0 ? null : index;
}

/**
 * The timeline of one article with its date query and the selected version. A date asked for
 * selects the version in force that day (a gap or "not in force" selects nothing and is shown on
 * the timeline); the previous version for the difference is the nearest earlier one.
 */
export function TimelineExplorer({
    timeline,
    latestSnapshotDate,
}: {
    timeline: TimelineEntry[];
    latestSnapshotDate: string;
}) {
    const t = useTranslations("review.statutes.timeline");
    const [selected, setSelected] = useState(() => lastVersion(timeline));
    const [day, setDay] = useState("");
    const result = ISO_DAY.test(day) ? statuteAsOf(timeline, day, latestSnapshotDate) : null;

    function ask(value: string) {
        setDay(value);
        if (!ISO_DAY.test(value)) return;
        const answer = statuteAsOf(timeline, value, latestSnapshotDate);
        if (answer.index !== null && timeline[answer.index]?.kind === "version") {
            setSelected(answer.index);
        }
    }

    const current = selected === null ? undefined : timeline[selected];
    const previousIndex =
        selected === null
            ? -1
            : timeline.findLastIndex(
                  (entry, index) => index < selected && entry.kind === "version",
              );
    const previous = timeline[previousIndex];
    const gapBetween =
        selected !== null &&
        previousIndex >= 0 &&
        timeline.slice(previousIndex + 1, selected).some((entry) => entry.kind === "gap");

    return (
        <>
            <DateQuery
                day={day}
                result={result}
                timeline={timeline}
                latestSnapshotDate={latestSnapshotDate}
                onChange={ask}
            />
            <Card>
                <CardHeader>
                    <CardTitle>{t("title")}</CardTitle>
                </CardHeader>
                <CardContent>
                    <TimelineList
                        timeline={timeline}
                        selected={selected}
                        matched={result?.index ?? null}
                        onSelect={setSelected}
                    />
                </CardContent>
            </Card>
            {current?.kind === "version" ? (
                <VersionPanel
                    version={current}
                    previous={previous?.kind === "version" ? previous : null}
                    gapBetween={gapBetween}
                />
            ) : null}
        </>
    );
}
