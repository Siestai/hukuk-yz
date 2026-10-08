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
export const SORTS = ["score_asc", "score_desc", "reviewed_desc"] as const;
/** The tabs of the list, in order; `pending` is the queue itself. */
export const STATUSES = ["pending", "approved", "rejected", "all"] as const;
/** The `durum` value of each tab in the URL; the queue (pending) has none. */
export const STATUS_SLUGS = { approved: "onaylanan", rejected: "reddedilen", all: "tumu" } as const;

export type Band = (typeof BANDS)[number];
export type Sort = (typeof SORTS)[number];
export type QueueStatus = (typeof STATUSES)[number];

/** The sorts a tab offers: nothing was reviewed yet in the queue, so it cannot sort by review. */
export function sortsFor(status: QueueStatus): readonly Sort[] {
    return status === "pending" ? ["score_asc", "score_desc"] : SORTS;
}

/** Newest review first where everything was reviewed, most suspicious first elsewhere. */
export function defaultSort(status: QueueStatus): Sort {
    return status === "approved" || status === "rejected" ? "reviewed_desc" : "score_asc";
}

export type QueueParams = {
    /** The tab; absent is the queue (`pending`), like the other defaults left out of the URL. */
    status?: Exclude<QueueStatus, "pending">;
    band?: Band;
    court?: string;
    reason?: string;
    journalIssue?: number;
    q?: string;
    sort: Sort;
    page: number;
};

export function statusOf(params: QueueParams): QueueStatus {
    return params.status ?? "pending";
}

/** What a filter control may change; the page is reset unless the change names one. */
export type QueueChange = Partial<QueueParams>;

export type RawParams = URLSearchParams | Record<string, string | string[] | undefined>;

export const MAX_PAGE = 100_000;
export const MAX_JOURNAL_ISSUE = 10_000;
export const MAX_QUERY_LENGTH = 100;

export function pick(raw: RawParams, key: string): string | undefined {
    const value = raw instanceof URLSearchParams ? (raw.get(key) ?? undefined) : raw[key];
    return Array.isArray(value) ? value[0] : value;
}

export function oneOf<T extends string>(
    values: readonly T[],
    value: string | undefined,
): T | undefined {
    return values.find((candidate) => candidate === value);
}

export function positiveInt(value: string | undefined, max: number): number | undefined {
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
    const slug = pick(raw, "durum");
    const status = (Object.keys(STATUS_SLUGS) as (keyof typeof STATUS_SLUGS)[]).find(
        (key) => STATUS_SLUGS[key] === slug,
    );
    return {
        ...(status && { status }),
        band: oneOf(BANDS, pick(raw, "band")),
        court: court === UNKNOWN_COURT ? court : oneOf(COURTS, court),
        reason: reason && /^[a-z0-9_]{1,64}$/.test(reason) ? reason : undefined,
        journalIssue: parseJournalIssue(pick(raw, "journal_issue") ?? ""),
        q: pick(raw, "q")?.trim().slice(0, MAX_QUERY_LENGTH) || undefined,
        sort:
            oneOf(sortsFor(status ?? "pending"), pick(raw, "sort")) ??
            defaultSort(status ?? "pending"),
        page: positiveInt(pick(raw, "page"), MAX_PAGE) ?? 1,
    };
}

/** The URL query of a state; defaults (the queue tab, the tab's sort, first page) are left out. */
export function serializeQueueParams(params: QueueParams): URLSearchParams {
    const query = new URLSearchParams();
    if (params.status) query.set("durum", STATUS_SLUGS[params.status]);
    if (params.band) query.set("band", params.band);
    if (params.court) query.set("court", params.court);
    if (params.reason) query.set("reason", params.reason);
    if (params.journalIssue) query.set("journal_issue", String(params.journalIssue));
    if (params.q) query.set("q", params.q);
    if (params.sort !== defaultSort(statusOf(params))) query.set("sort", params.sort);
    if (params.page > 1) query.set("page", String(params.page));
    return query;
}

/** What a review action leaves behind for the next screen to announce. */
export const FLASHES = ["approved", "edited", "rejected"] as const;
export type Flash = (typeof FLASHES)[number];
export type Notice = { flash?: Flash; done?: boolean };

const MAX_POSITION = MAX_PAGE * PAGE_SIZE;

/** The absolute index of a record in the queue (filters and sort applied), carried by detail links. */
export function parsePosition(raw: RawParams): number | undefined {
    const value = pick(raw, "pos");
    if (!value || !/^(0|[1-9]\d{0,8})$/.test(value)) return undefined;
    const n = Number(value);
    return n <= MAX_POSITION ? n : undefined;
}

export function parseNotice(raw: RawParams): Notice {
    return { flash: oneOf(FLASHES, pick(raw, "flash")), done: pick(raw, "done") === "1" };
}

export function withNotice(query: URLSearchParams, notice: Notice = {}): string {
    if (notice.flash) query.set("flash", notice.flash);
    if (notice.done) query.set("done", "1");
    return query.toString();
}

export function queueHref(params: QueueParams, notice?: Notice): string {
    const query = withNotice(serializeQueueParams(params), notice);
    return query ? `/?${query}` : "/";
}

/**
 * The detail screen of an extraction; it carries the queue state so "back" and the next record
 * keep the filters, and `pos` (the record's index in that queue) so the next record can be
 * found even after this one has left the queue.
 */
export function detailHref(
    extractionId: string,
    params: QueueParams,
    extra: { pos?: number; flash?: Flash } = {},
): string {
    const query = serializeQueueParams(params);
    if (extra.pos !== undefined) query.set("pos", String(extra.pos));
    const text = withNotice(query, { flash: extra.flash });
    return `/kararlar/${extractionId}${text ? `?${text}` : ""}`;
}

/** The state of a tab: the filters stay, the sort is the tab's own and the page the first. */
export function tabParams(params: QueueParams, status: QueueStatus): QueueParams {
    return {
        ...params,
        status: status === "pending" ? undefined : status,
        sort: defaultSort(status),
        page: 1,
    };
}

/** Applies a change; any change that does not name a page goes back to page 1. */
export function changeQueueParams(params: QueueParams, change: QueueChange): QueueParams {
    return { ...params, ...change, page: change.page ?? 1 };
}

/** How many of the filters (band, court, reason, journal issue, search) are set. */
export function activeFilterCount(params: QueueParams): number {
    return [params.band, params.court, params.reason, params.journalIssue, params.q].filter(Boolean)
        .length;
}

export function hasFilters(params: QueueParams): boolean {
    return activeFilterCount(params) > 0;
}

/** The `/review/decisions` query of a state. */
export function apiQuery(params: QueueParams) {
    return {
        status: params.status,
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
