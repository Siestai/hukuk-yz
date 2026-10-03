"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { BANDS, type Band } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useQueueNavigation } from "./use-queue-navigation";

const BAR_HEIGHT = 4;
const segmentClass = { high: "fill-high", medium: "fill-medium", low: "fill-low" } as const;
const swatchClass = { high: "bg-high", medium: "bg-medium", low: "bg-low" } as const;

export type BandSegment = { band: Band; x: number; width: number };

/** Segments of a 0-100 wide bar, in band order; empty when nothing is pending. */
export function bandSegments(counts: Record<Band, number>): BandSegment[] {
    const total = BANDS.reduce((sum, band) => sum + counts[band], 0);
    if (total === 0) return [];
    let x = 0;
    return BANDS.map((band) => {
        const width = (counts[band] / total) * 100;
        const segment = { band, x, width };
        x += width;
        return segment;
    });
}

export function BandDistribution({ counts }: { counts: Record<Band, number> }) {
    const t = useTranslations("review.queue.summary");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { params, navigate } = useQueueNavigation();
    const details = BANDS.map((band) =>
        t("bandCount", { band: labels.band(band), count: counts[band] }),
    ).join(", ");

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("bandTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
                <svg
                    role="img"
                    aria-label={t("bandChart", { details })}
                    viewBox={`0 0 100 ${BAR_HEIGHT}`}
                    preserveAspectRatio="none"
                    className="h-3 w-full rounded-sm"
                >
                    <rect width={100} height={BAR_HEIGHT} className="fill-sunken" />
                    {bandSegments(counts).map(({ band, x, width }) => (
                        <rect
                            key={band}
                            x={x}
                            width={width}
                            height={BAR_HEIGHT}
                            className={segmentClass[band]}
                        />
                    ))}
                </svg>
                <div className="grid grid-cols-3 gap-2">
                    {BANDS.map((band) => (
                        <button
                            key={band}
                            type="button"
                            aria-pressed={params.band === band}
                            onClick={() =>
                                navigate({ band: params.band === band ? undefined : band })
                            }
                            className="grid gap-1 rounded-md p-2 text-left hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-ring aria-pressed:bg-primary-soft"
                        >
                            <span className="font-mono text-lg font-medium text-ink">
                                {format.number(counts[band], "integer")}
                            </span>
                            <span className="flex items-center gap-2 text-xs text-ink-2">
                                <span className={`size-2 rounded-sm ${swatchClass[band]}`} />
                                {labels.band(band)}
                            </span>
                        </button>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}
