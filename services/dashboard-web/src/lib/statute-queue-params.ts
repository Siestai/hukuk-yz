import {
    BANDS,
    MAX_PAGE,
    MAX_QUERY_LENGTH,
    oneOf,
    pick,
    positiveInt,
    STATUS_SLUGS,
    withNotice,
    PAGE_SIZE,
    type Band,
    type Notice,
    type QueueStatus,
    type RawParams,
    type Flash,
} from "./queue-params";

/** The statutes the screen reviews, in tab order; the first is the default. */
export const STATUTES = ["4857", "5510"] as const;
export type StatuteNo = (typeof STATUTES)[number];

/**
 * The state of the statute queue in the URL. `kind` tells it from the decision queue's state where
 * both go through the same components; it is not in the URL. Same params as the decision queue
 * where they mean the same (`durum`, `band`, `q`, `page`), plus `kanun` (4857 is left out).
 */
export type StatuteQueueParams = {
    kind: "statute";
    status?: Exclude<QueueStatus, "pending">;
    band?: Band;
    statute: StatuteNo;
    q?: string;
    page: number;
};

export type StatuteQueueChange = Partial<StatuteQueueParams>;

const DEFAULT_STATUTE: StatuteNo = STATUTES[0];

/** Reads the statute queue state from a URL; anything unknown or malformed is ignored. */
export function parseStatuteParams(raw: RawParams): StatuteQueueParams {
    const slug = pick(raw, "durum");
    const status = (Object.keys(STATUS_SLUGS) as (keyof typeof STATUS_SLUGS)[]).find(
        (key) => STATUS_SLUGS[key] === slug,
    );
    return {
        kind: "statute",
        ...(status && { status }),
        band: oneOf(BANDS, pick(raw, "band")),
        statute: oneOf(STATUTES, pick(raw, "kanun")) ?? DEFAULT_STATUTE,
        q: pick(raw, "q")?.trim().slice(0, MAX_QUERY_LENGTH) || undefined,
        page: positiveInt(pick(raw, "page"), MAX_PAGE) ?? 1,
    };
}

/** The URL query of a state; defaults (the queue tab, 4857, first page) are left out. */
export function serializeStatuteParams(params: StatuteQueueParams): URLSearchParams {
    const query = new URLSearchParams();
    if (params.status) query.set("durum", STATUS_SLUGS[params.status]);
    if (params.statute !== DEFAULT_STATUTE) query.set("kanun", params.statute);
    if (params.band) query.set("band", params.band);
    if (params.q) query.set("q", params.q);
    if (params.page > 1) query.set("page", String(params.page));
    return query;
}

export function statuteListHref(params: StatuteQueueParams, notice?: Notice): string {
    const query = withNotice(serializeStatuteParams(params), notice);
    return query ? `/mevzuat?${query}` : "/mevzuat";
}

/** The detail screen of an article; like the decision one it carries the queue state and `pos`. */
export function statuteDetailHref(
    extractionId: string,
    params: StatuteQueueParams,
    extra: { pos?: number; flash?: Flash } = {},
): string {
    const query = serializeStatuteParams(params);
    if (extra.pos !== undefined) query.set("pos", String(extra.pos));
    const text = withNotice(query, { flash: extra.flash });
    return `/mevzuat/${extractionId}${text ? `?${text}` : ""}`;
}

/** The state of a tab: the filters stay and the first page opens. */
export function statuteTabParams(
    params: StatuteQueueParams,
    status: QueueStatus,
): StatuteQueueParams {
    return { ...params, status: status === "pending" ? undefined : status, page: 1 };
}

export function changeStatuteParams(
    params: StatuteQueueParams,
    change: StatuteQueueChange,
): StatuteQueueParams {
    return { ...params, ...change, page: change.page ?? 1 };
}

/** The filters set: band and search (the statute is a tab). */
export function activeStatuteFilterCount(params: StatuteQueueParams): number {
    return [params.band, params.q].filter(Boolean).length;
}

/** The `/review/statutes` query of a state. */
export function statuteApiQuery(params: StatuteQueueParams) {
    return {
        status: params.status,
        band: params.band,
        statute: params.statute,
        q: params.q,
        limit: PAGE_SIZE,
        offset: (params.page - 1) * PAGE_SIZE,
    };
}
