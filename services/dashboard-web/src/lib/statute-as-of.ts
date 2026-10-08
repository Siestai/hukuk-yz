import type { components } from "@/lib/api/schema";

export type TimelineVersion = components["schemas"]["TimelineVersion"];
export type TimelineGap = components["schemas"]["TimelineGap"];
export type TimelineEntry = TimelineVersion | TimelineGap;

/**
 * What an article said on a date, read off its timeline: the same rule as `as_of` of the ingest
 * package (`hukuk_ingest.statutes.timeline`) and the API of task 11b. Every interval is half open,
 * `[from, to)`: the day a version ends is already the next one's. A version wins over a gap; a
 * repealed version is `not_in_force` with the reason. `index` is the entry in `timeline` (null
 * when none applies). `stale`: the date is after the newest snapshot, so the text may have been
 * amended since.
 */
export type AsOfResult =
    | { status: "found"; index: number; stale: boolean }
    | { status: "gap"; index: number; stale: boolean }
    | { status: "not_in_force"; reason: "repealed" | null; index: number | null; stale: boolean };

/** Dates are ISO `YYYY-MM-DD`, which sort as text. */
function covers(from: string | null, to: string | null, day: string): boolean {
    return (from === null || from <= day) && (to === null || day < to);
}

export function statuteAsOf(
    timeline: TimelineEntry[],
    day: string,
    latestSnapshotDate: string,
): AsOfResult {
    const stale = day > latestSnapshotDate;
    const version = timeline.findIndex(
        (entry) => entry.kind === "version" && covers(entry.valid_from, entry.valid_to, day),
    );
    const found = timeline[version];
    if (found?.kind === "version") {
        return found.change_kind === "repealed"
            ? { status: "not_in_force", reason: "repealed", index: version, stale }
            : { status: "found", index: version, stale };
    }
    const gap = timeline.findIndex(
        (entry) => entry.kind === "gap" && covers(entry.from, entry.to, day),
    );
    if (gap >= 0) return { status: "gap", index: gap, stale };
    return { status: "not_in_force", reason: null, index: null, stale };
}
