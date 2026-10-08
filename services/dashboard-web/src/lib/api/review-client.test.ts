import { describe, expect, it, vi } from "vitest";

import type { createApiClient } from "./client";
import {
    ApiFailure,
    locate,
    neighbour,
    nextAfter,
    postReview,
    postReviewIn,
} from "./review-client";

const queue = { band: "low", sort: "score_asc", page: 2 } as const;

function api(items: string[], total = 100) {
    const GET = vi.fn(
        async (_path: string, init: { params: { query: Record<string, unknown> } }) => {
            const { offset, limit } = init.params.query as { offset: number; limit: number };
            return {
                data: {
                    total,
                    items: items
                        .slice(offset - 50, offset - 50 + limit)
                        .map((id) => ({ extraction_id: id })),
                },
            };
        },
    );
    return { client: { GET } as unknown as ReturnType<typeof createApiClient>, GET };
}

const query = (call: unknown[]) => (call[1] as { params: { query: unknown } }).params.query;

describe("locate", () => {
    it("trusts a position only when the record at that index is this one", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await locate(client, queue, "b", 51)).toBe(51);
        expect(query(GET.mock.calls[0] as unknown[])).toMatchObject({
            band: "low",
            sort: "score_asc",
            limit: 1,
            offset: 51,
        });
    });

    it("falls back to the page window when the position points at another record", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await locate(client, queue, "c", 50)).toBe(52);
        expect(query(GET.mock.calls[1] as unknown[])).toMatchObject({ limit: 50, offset: 50 });
    });

    it("falls back to the page window without a position", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await locate(client, queue, "b", undefined)).toBe(51);
        expect(GET).toHaveBeenCalledTimes(1);
        expect(query(GET.mock.calls[0] as unknown[])).toMatchObject({ limit: 50, offset: 50 });
    });

    it("is null when the record is in neither place", async () => {
        const { client } = api(["a"]);
        expect(await locate(client, queue, "missing", 50)).toBeNull();
        expect(await locate(client, queue, "missing", undefined)).toBeNull();
    });
});

describe("neighbour", () => {
    it("next is one place after the record, previous one before", async () => {
        const { client } = api(["a", "b", "c"]);
        expect(await neighbour(client, queue, "b", 51, 1)).toEqual({
            kind: "record",
            id: "c",
            pos: 52,
        });
        expect(await neighbour(client, queue, "b", 51, -1)).toEqual({
            kind: "record",
            id: "a",
            pos: 50,
        });
    });

    it("is an edge past the end of the queue", async () => {
        const { client } = api(["a"]);
        expect(await neighbour(client, queue, "a", 50, 1)).toEqual({ kind: "edge" });
    });

    it("K on the first record is an edge", async () => {
        const GET = vi.fn(async () => ({ data: { total: 1, items: [{ extraction_id: "a" }] } }));
        const client = { GET } as unknown as ReturnType<typeof createApiClient>;
        expect(await neighbour(client, { ...queue, page: 1 }, "a", 0, -1)).toEqual({
            kind: "edge",
        });
    });

    it("is unknown when the record is not in the queue", async () => {
        const { client } = api(["a"]);
        expect(await neighbour(client, queue, "missing", undefined, 1)).toEqual({
            kind: "unknown",
        });
    });
});

describe("nextAfter", () => {
    it("is whatever now sits at the old position", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await nextAfter(client, queue, 51)).toEqual({ id: "b", pos: 51 });
        expect(GET).toHaveBeenCalledTimes(1);
    });

    it("starts over from the top when the record was the last of the queue", async () => {
        const GET = vi.fn(
            async (_path: string, init: { params: { query: Record<string, unknown> } }) => ({
                data: {
                    total: 3,
                    items: init.params.query.offset === 0 ? [{ extraction_id: "first" }] : [],
                },
            }),
        );
        const client = { GET } as unknown as ReturnType<typeof createApiClient>;
        expect(await nextAfter(client, queue, 7)).toEqual({ id: "first", pos: 0 });
    });

    it("is null only when offset 0 returns nothing", async () => {
        const GET = vi.fn(async () => ({ data: { total: 0, items: [] } }));
        const client = { GET } as unknown as ReturnType<typeof createApiClient>;
        expect(await nextAfter(client, queue, 7)).toBeNull();
        expect(GET).toHaveBeenCalledTimes(2);
        expect(await nextAfter(client, queue, 0)).toBeNull();
        expect(GET).toHaveBeenCalledTimes(3);
    });

    it("lets a failed lookup through instead of answering empty", async () => {
        const GET = vi.fn(async () => {
            throw new TypeError("fetch failed");
        });
        const client = { GET } as unknown as ReturnType<typeof createApiClient>;
        await expect(nextAfter(client, queue, 7)).rejects.toMatchObject({
            code: "upstream_unavailable",
        });
    });
});

describe("calls", () => {
    it("turn an error body into an ApiFailure with its code and params", async () => {
        const POST = vi.fn(async () => ({
            error: { error: { code: "decision_conflict", params: { decision_id: "d1" } } },
        }));
        const client = { POST } as unknown as ReturnType<typeof createApiClient>;
        await expect(postReview(client, "x", { action: "approve" })).rejects.toMatchObject({
            code: "decision_conflict",
            params: { decision_id: "d1" },
        });
    });

    it("report a lost connection as upstream_unavailable", async () => {
        const POST = vi.fn(async () => {
            throw new TypeError("fetch failed");
        });
        const client = { POST } as unknown as ReturnType<typeof createApiClient>;
        const failure = await postReview(client, "x", { action: "approve" }).catch(
            (e: unknown) => e,
        );
        expect(failure).toBeInstanceOf(ApiFailure);
        expect(failure).toMatchObject({ code: "upstream_unavailable" });
    });
});

describe("the statute queue", () => {
    const statutes = {
        kind: "statute",
        statute: "5510",
        band: "high",
        page: 2,
    } as const;

    it("is listed from /review/statutes with its own query, and locates a record in it", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await locate(client, statutes, "b", 51)).toBe(51);
        expect(GET.mock.calls[0]?.[0]).toBe("/review/statutes");
        expect(query(GET.mock.calls[0] as unknown[])).toEqual({
            status: undefined,
            band: "high",
            statute: "5510",
            q: undefined,
            limit: 1,
            offset: 51,
        });
        expect(await locate(client, statutes, "c", undefined)).toBe(52);
        expect(query(GET.mock.calls[1] as unknown[])).toMatchObject({ limit: 50, offset: 50 });
    });

    it("finds the neighbours and the next record after an article has left it", async () => {
        const { client } = api(["a", "b", "c"]);
        expect(await neighbour(client, statutes, "b", 51, 1)).toEqual({
            kind: "record",
            id: "c",
            pos: 52,
        });
        expect(await nextAfter(client, statutes, 51)).toEqual({ id: "b", pos: 51 });
    });

    it("posts the action to the statute endpoint, and never an edit", async () => {
        const POST = vi.fn().mockResolvedValue({ data: { review_id: "r" } });
        const client = { POST } as unknown as ReturnType<typeof createApiClient>;
        await postReviewIn(client, statutes, "e1", { action: "reject", note: "yanlış" });
        expect(POST).toHaveBeenCalledWith("/review/statutes/{extraction_id}", {
            params: { path: { extraction_id: "e1" } },
            body: { action: "reject", note: "yanlış" },
        });
        expect(() => postReviewIn(client, statutes, "e1", { action: "edit", edits: {} })).toThrow(
            "not edited",
        );
        await postReviewIn(client, queue, "e2", { action: "approve" });
        expect(POST).toHaveBeenLastCalledWith("/review/decisions/{extraction_id}", {
            params: { path: { extraction_id: "e2" } },
            body: { action: "approve" },
        });
    });
});
