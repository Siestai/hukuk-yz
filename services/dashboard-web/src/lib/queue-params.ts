export const PAGE_SIZE = 50;
export const BANDS = ["high", "medium", "low"] as const;
export const COURTS = [
    "aym",
    "yargitay",
    "danistay",
    "bam",
    "bim",
    "ilk_derece",
    "aihm",
    "abad",
    "foreign",
] as const;
/** URL value for decisions whose court could not be read; the API filters it as `court=""`. */
export const UNKNOWN_COURT = "unknown";
export const SORTS = ["score_asc", "score_desc"] as const;

export type Band = (typeof BANDS)[number];
export type Sort = (typeof SORTS)[number];

export type QueueParams = {
    band?: Band;
    court?: string;
    reason?: string;
    journalIssue?: number;
    q?: string;
    sort: Sort;
    page: number;
};

/** What a filter control may change; the page is reset unless the change names one. */
export type QueueChange = Partial<QueueParams>;

type RawParams = URLSearchParams | Record<string, string | string[] | undefined>;

const MAX_PAGE = 100_000;
export const MAX_JOURNAL_ISSUE = 10_000;
const MAX_QUERY_LENGTH = 100;

function pick(raw: RawParams, key: string): string | undefined {
    const value = raw instanceof URLSearchParams ? (raw.get(key) ?? undefined) : raw[key];
    return Array.isArray(value) ? value[0] : value;
}

function oneOf<T extends string>(values: readonly T[], value: string | undefined): T | undefined {
    return values.find((candidate) => candidate === value);
}

function positiveInt(value: string | undefined, max: number): number | undefined {
    if (!value || !/^\d{1,9}$/.test(value)) return undefined;
    const n = Number(value);
    return n >= 1 && n <= max ? n : undefined;
}

/** A journal issue typed by a person: digits only, within range. */
export function parseJournalIssue(value: string): number | undefined {
    return positiveInt(value.trim(), MAX_JOURNAL_ISSUE);
}

/** Reads the queue state from a URL; anything unknown or malformed is ignored. */
export function parseQueueParams(raw: RawParams): QueueParams {
    const court = pick(raw, "court");
    const reason = pick(raw, "reason");
    return {
        band: oneOf(BANDS, pick(raw, "band")),
        court: court === UNKNOWN_COURT ? court : oneOf(COURTS, court),
        reason: reason && /^[a-z0-9_]{1,64}$/.test(reason) ? reason : undefined,
        journalIssue: parseJournalIssue(pick(raw, "journal_issue") ?? ""),
        q: pick(raw, "q")?.trim().slice(0, MAX_QUERY_LENGTH) || undefined,
        sort: oneOf(SORTS, pick(raw, "sort")) ?? "score_asc",
        page: positiveInt(pick(raw, "page"), MAX_PAGE) ?? 1,
    };
}

/** The URL query of a state; defaults (first page, most suspicious first) are left out. */
export function serializeQueueParams(params: QueueParams): URLSearchParams {
    const query = new URLSearchParams();
    if (params.band) query.set("band", params.band);
    if (params.court) query.set("court", params.court);
    if (params.reason) query.set("reason", params.reason);
    if (params.journalIssue) query.set("journal_issue", String(params.journalIssue));
    if (params.q) query.set("q", params.q);
    if (params.sort !== "score_asc") query.set("sort", params.sort);
    if (params.page > 1) query.set("page", String(params.page));
    return query;
}

export function queueHref(params: QueueParams): string {
    const query = serializeQueueParams(params).toString();
    return query ? `/?${query}` : "/";
}

/** Applies a change; any change that does not name a page goes back to page 1. */
export function changeQueueParams(params: QueueParams, change: QueueChange): QueueParams {
    return { ...params, ...change, page: change.page ?? 1 };
}

export function hasFilters(params: QueueParams): boolean {
    return Boolean(params.band || params.court || params.reason || params.journalIssue || params.q);
}

/** The `/review/decisions` query of a state. */
export function apiQuery(params: QueueParams) {
    return {
        band: params.band,
        court: params.court === UNKNOWN_COURT ? "" : params.court,
        reason: params.reason,
        journal_issue: params.journalIssue,
        q: params.q,
        sort: params.sort,
        limit: PAGE_SIZE,
        offset: (params.page - 1) * PAGE_SIZE,
    };
}
