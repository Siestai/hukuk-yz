import { apiError } from "./errors";
import type { createApiClient } from "./client";
import type { components } from "./schema";
import { apiQuery, type QueueParams } from "@/lib/queue-params";

type Api = ReturnType<typeof createApiClient>;
type Answer<T> = { data?: T; error?: unknown };

/** A failed call of the client: the stable error code of the API (or of the BFF) and its params. */
export class ApiFailure extends Error {
    constructor(
        readonly code: string | undefined,
        readonly params: Record<string, unknown> = {},
    ) {
        super(code ?? "api_failure");
        this.name = "ApiFailure";
    }
}

async function unwrap<T>(request: Promise<Answer<T>>): Promise<T> {
    const answer = await request.catch(() => {
        throw new ApiFailure("upstream_unavailable");
    });
    if (answer.data === undefined) {
        const { code, params } = apiError(answer.error);
        throw new ApiFailure(code, params);
    }
    return answer.data;
}

export type ReviewAction = components["schemas"]["ReviewActionRequest"];

export function postReview(api: Api, extractionId: string, body: ReviewAction) {
    return unwrap(
        api.POST("/review/decisions/{extraction_id}", {
            params: { path: { extraction_id: extractionId } },
            body,
        }),
    );
}

/** The record at an absolute index of the queue, or null past its end. */
async function recordAt(api: Api, queue: QueueParams, pos: number): Promise<string | null> {
    if (pos < 0) return null;
    const list = await unwrap(
        api.GET("/review/decisions", {
            params: { query: { ...apiQuery(queue), limit: 1, offset: pos } },
        }),
    );
    return list.items[0]?.extraction_id ?? null;
}

/**
 * The index of a record in its queue. The `pos` of the link that led here is only a hint (anyone
 * can edit a URL, and the queue moves): it counts when the record at that index is this one,
 * otherwise the record is looked up in the page window of the queue state. Null when it is not
 * in the queue (any more).
 */
export async function locate(
    api: Api,
    queue: QueueParams,
    extractionId: string,
    pos: number | undefined,
): Promise<number | null> {
    if (pos !== undefined && (await recordAt(api, queue, pos)) === extractionId) return pos;
    const query = apiQuery(queue);
    const list = await unwrap(api.GET("/review/decisions", { params: { query } }));
    const index = list.items.findIndex((item) => item.extraction_id === extractionId);
    return index < 0 ? null : query.offset + index;
}

export type Neighbour = { id: string; pos: number };
/** Where a move leads: to a record, past either end of the queue, or nowhere known. */
export type Move = ({ kind: "record" } & Neighbour) | { kind: "edge" } | { kind: "unknown" };

/** The record after (`1`) or before (`-1`) this one in a queue state; it must still be in the queue. */
export async function neighbour(
    api: Api,
    queue: QueueParams,
    extractionId: string,
    pos: number | undefined,
    step: -1 | 1,
): Promise<Move> {
    const at = await locate(api, queue, extractionId, pos);
    if (at === null) return { kind: "unknown" };
    const id = await recordAt(api, queue, at + step);
    return id === null ? { kind: "edge" } : { kind: "record", id, pos: at + step };
}

/**
 * Where to go once the record at `at` has left the queue: whatever now sits at that index is the
 * next one; past the end the queue starts over from its top; `null` means it is empty.
 */
export async function nextAfter(
    api: Api,
    queue: QueueParams,
    at: number,
): Promise<Neighbour | null> {
    for (const pos of at === 0 ? [0] : [at, 0]) {
        const id = await recordAt(api, queue, pos);
        if (id !== null) return { id, pos };
    }
    return null;
}
