import { describe, expect, it, vi } from "vitest";

import type { createApiClient } from "./client";
import { ApiFailure, locate, neighbour, postReview } from "./review-client";

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

describe("neighbour", () => {
    it("after an action asks for whatever now sits at the same position, with the queue filters", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await neighbour(client, queue, "gone", 51, 0)).toEqual({ id: "b", pos: 51 });
        expect(query(GET.mock.calls[0] as unknown[])).toMatchObject({
            band: "low",
            sort: "score_asc",
            limit: 1,
            offset: 51,
        });
    });

    it("next is one place after the position, previous one before", async () => {
        const { client } = api(["a", "b", "c"]);
        expect(await neighbour(client, queue, "b", 51, 1)).toEqual({ id: "c", pos: 52 });
        expect(await neighbour(client, queue, "b", 51, -1)).toEqual({ id: "a", pos: 50 });
    });

    it("is null at the end of the queue and before its start", async () => {
        const { client } = api(["a"]);
        expect(await neighbour(client, queue, "a", 50, 1)).toBeNull();
        expect(await neighbour(client, queue, "a", 0, -1)).toBeNull();
    });

    it("without a position finds the record in the page window", async () => {
        const { client, GET } = api(["a", "b", "c"]);
        expect(await neighbour(client, queue, "b", undefined, 1)).toEqual({ id: "c", pos: 52 });
        expect(query(GET.mock.calls[0] as unknown[])).toMatchObject({ limit: 50, offset: 50 });
    });

    it("is null when the record is not in the window and there is no position", async () => {
        const { client } = api(["a"]);
        expect(await neighbour(client, queue, "missing", undefined, 1)).toBeNull();
        expect(await locate(client, queue, "missing", undefined)).toBeNull();
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
