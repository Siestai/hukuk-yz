import type { components } from "@/lib/api/schema";
import { BANDS, type Band } from "@/lib/queue-params";
import { STATUTES, type StatuteNo } from "@/lib/statute-queue-params";

type Row = components["schemas"]["StatuteSummaryRow"];

export type StatuteSummary = {
    /** The articles still waiting, by band, of the statute on screen. */
    bands: Record<Band, number>;
    pending: number;
    approved: number;
    rejected: number;
    /** The articles waiting in each statute, for the statute tabs. */
    waiting: Record<StatuteNo, number>;
};

/** The counts of the screen from the rows of `GET /review/statutes/summary`, for one statute. */
export function summarizeStatutes(rows: Row[], statute: StatuteNo): StatuteSummary {
    const summary: StatuteSummary = {
        bands: Object.fromEntries(BANDS.map((band) => [band, 0])) as Record<Band, number>,
        pending: 0,
        approved: 0,
        rejected: 0,
        waiting: Object.fromEntries(STATUTES.map((number) => [number, 0])) as Record<
            StatuteNo,
            number
        >,
    };
    for (const row of rows) {
        const number = STATUTES.find((candidate) => candidate === row.statute_number);
        if (number && row.status === "pending") summary.waiting[number] += row.count;
        if (number !== statute) continue;
        if (row.status === "pending") {
            summary.pending += row.count;
            summary.bands[row.band] += row.count;
        } else {
            summary[row.status] += row.count;
        }
    }
    return summary;
}
