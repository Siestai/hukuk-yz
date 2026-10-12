import type { FileOut } from "@/lib/files";
import { isUuid } from "@/lib/uuid";

/** The fields of the approval form that detection can suggest (`issuer` has no field to write). */
export const SUGGESTION_FIELDS = ["doc_type", "doc_date", "official_ref", "title"] as const;
export type SuggestionField = (typeof SUGGESTION_FIELDS)[number];

export const SUGGESTION_SOURCES = ["rule", "llm", "user"] as const;
export type SuggestionSource = (typeof SUGGESTION_SOURCES)[number];

export const MATCH_REASONS = ["same_ref", "same_title", "same_name"] as const;

export type Suggestion = {
    value: string;
    source: SuggestionSource;
    /** Where in the text the value was read; null when the evidence is not a quote (or there is none). */
    quote: { page: number; text: string } | null;
    /** An LLM answer nothing in the text supports: the screen warns. */
    unsupported: boolean;
    /** What detection found when the user typed another value at the upload. */
    detected?: { value: string };
};

export type Suggestions = Partial<Record<SuggestionField, Suggestion>>;

const isRecord = (value: unknown): value is Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value);

function readSuggestion(raw: unknown): Suggestion | undefined {
    if (!isRecord(raw) || typeof raw.value !== "string" || raw.value === "") return undefined;
    const source = SUGGESTION_SOURCES.find((candidate) => candidate === raw.source);
    if (!source) return undefined;
    const evidence = isRecord(raw.evidence) ? raw.evidence : null;
    const quote =
        evidence && typeof evidence.page === "number" && typeof evidence.quote === "string"
            ? { page: evidence.page, text: evidence.quote }
            : null;
    const detected =
        isRecord(raw.detected) && typeof raw.detected.value === "string"
            ? { value: raw.detected.value }
            : undefined;
    return {
        value: raw.value,
        source,
        quote,
        unsupported: source === "llm" && evidence === null,
        ...(detected ? { detected } : {}),
    };
}

/** The worker's `suggestions` (free-form JSON) as the fields the form shows; malformed entries are dropped. */
export function readSuggestions(raw: FileOut["suggestions"]): Suggestions {
    const out: Suggestions = {};
    for (const field of SUGGESTION_FIELDS) {
        const suggestion = readSuggestion(raw?.[field]);
        if (suggestion) out[field] = suggestion;
    }
    return out;
}

export type FileMatches = {
    previous: { fileId: string; reason: string } | null;
    similar: { fileId: string; score: number; reason: string }[];
};

/** The worker's `matches` (free-form JSON); an entry without a file id is dropped. */
export function readMatches(raw: FileOut["matches"]): FileMatches {
    const previous = isRecord(raw?.previous_version) ? raw.previous_version : null;
    const similar = Array.isArray(raw?.similar) ? raw.similar : [];
    return {
        previous:
            previous && typeof previous.file_id === "string" && isUuid(previous.file_id)
                ? { fileId: previous.file_id, reason: String(previous.reason ?? "") }
                : null,
        similar: similar.flatMap((entry: unknown) =>
            isRecord(entry) &&
            typeof entry.file_id === "string" &&
            isUuid(entry.file_id) &&
            typeof entry.score === "number"
                ? [
                      {
                          fileId: entry.file_id,
                          score: entry.score,
                          reason: String(entry.reason ?? ""),
                      },
                  ]
                : [],
        ),
    };
}
