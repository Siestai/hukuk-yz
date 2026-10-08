import type { TimelineVersion } from "./statute-as-of";

export type AmendingRef = { law: string; kabul: string | null };

/**
 * The amending acts of a version as the API words them: "6552 (10/9/2014), AYM (19/10/2005)"
 * (law and kabul day/month/year, each pair once). `kabul` is ISO; an entry that does not read
 * that way is kept with `kabul: null`.
 */
export function parseAmendingRef(ref: string | null): AmendingRef[] {
    if (!ref) return [];
    return ref.split(", ").map((part) => {
        const match = /^(.+) \((\d{1,2})\/(\d{1,2})\/(\d{4})\)$/.exec(part);
        if (!match) return { law: part, kabul: null };
        const [, law = part, day = "", month = "", year = ""] = match;
        return { law, kabul: `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}` };
    });
}

/** A law number ("6552") is a "sayılı Kanun"; anything else (AYM) is named as it is. */
export function isLawNumber(law: string): boolean {
    return /^\d+$/.test(law);
}

export type Evidence = {
    /** Where the start date comes from: `act` (the act's own date), `exception` or `fallback`. */
    basis: string | null;
    /** The copies that show this text, with their dates (same order). */
    copies: { fileName: string; date: string | null }[];
    amendments: AmendingRef[];
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null;

const strings = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];

/** Reads the `evidence` object of a version (the API leaves its keys open). */
export function readEvidence(version: TimelineVersion): Evidence {
    const raw = version.evidence;
    const paths = strings(raw.snapshots);
    const dates = strings(raw.snapshot_dates);
    return {
        basis: typeof raw.basis === "string" ? raw.basis : null,
        copies: paths.map((path, index) => ({
            fileName: path.split("/").at(-1) ?? path,
            date: dates[index] ?? null,
        })),
        amendments: parseAmendingRef(
            typeof raw.amendments === "string" ? raw.amendments : version.amending_ref,
        ),
    };
}

export type Footnote = { no: number; text: string; page: number | null };

/** Reads the footnotes of a version (`{no, text, page}`); an entry of another shape is skipped. */
export function readFootnotes(version: TimelineVersion): Footnote[] {
    return version.footnotes.flatMap((raw) =>
        isRecord(raw) && typeof raw.text === "string"
            ? [
                  {
                      no: typeof raw.no === "number" ? raw.no : 0,
                      text: raw.text,
                      page: typeof raw.page === "number" ? raw.page : null,
                  },
              ]
            : [],
    );
}
