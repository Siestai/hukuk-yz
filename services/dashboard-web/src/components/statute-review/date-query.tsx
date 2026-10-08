"use client";

import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId } from "react";

import type { AsOfResult, TimelineEntry } from "@/lib/statute-as-of";
import { DateQueryAnswer } from "./date-query-answer";

/**
 * "Bu madde şu tarihte nasıldı?": the date picker asks the timeline on screen (the same rule as
 * the API's `as_of`, `lib/statute-as-of.ts`) and the explorer selects and highlights the entry.
 */
export function DateQuery({
    day,
    result,
    timeline,
    latestSnapshotDate,
    onChange,
}: {
    day: string;
    result: AsOfResult | null;
    timeline: TimelineEntry[];
    latestSnapshotDate: string;
    onChange: (day: string) => void;
}) {
    const t = useTranslations("review.statutes.dateQuery");
    const id = useId();
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
                <div className="grid gap-1.5 md:w-56">
                    <Label htmlFor={id}>{t("date")}</Label>
                    <Input
                        id={id}
                        type="date"
                        value={day}
                        onChange={(event) => onChange(event.target.value)}
                    />
                </div>
                <div role="status">
                    {result ? (
                        <DateQueryAnswer
                            result={result}
                            timeline={timeline}
                            latestSnapshotDate={latestSnapshotDate}
                        />
                    ) : (
                        <p className="text-sm text-ink-2">{t("hint")}</p>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
