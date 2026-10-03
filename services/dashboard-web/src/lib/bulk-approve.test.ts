import { describe, expect, it, vi } from "vitest";

import { readRepoFile } from "@/test/reason-codes";
import { ApiFailure } from "./api/review-client";
import {
    BULK_FAILURE_CODES,
    bulkFailureCode,
    bulkFilters,
    isRetryable,
    resumeState,
    runBulk,
    startState,
    type BulkResponse,
} from "./bulk-approve";

const ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const SHA = (n: number) => String(n).repeat(64);
const answer = (over: Partial<BulkResponse>): BulkResponse => ({
    published: 0,
    conflicts: [],
    failed: [],
    remaining: 0,
    next_cursor: null,
    ...over,
});

function run(
    responses: (BulkResponse | ApiFailure)[],
    { total = 250, stopAfter = Infinity }: { total?: number; stopAfter?: number } = {},
) {
    const queue = [...responses];
    const request = vi.fn(async () => {
        const next = queue.shift();
        if (next instanceof ApiFailure) throw next;
        if (!next) throw new Error("unexpected call");
        return next;
    });
    const onProgress = vi.fn();
    const go = (state = startState(total)) =>
        runBulk({
            request,
            filters: { court: "bam" },
            state,
            onProgress,
            shouldStop: () => request.mock.calls.length >= stopAfter,
        });
    return { request, onProgress, go };
}

const body = (request: ReturnType<typeof run>["request"], call: number) =>
    (request.mock.calls[call] as unknown as [Record<string, unknown>])[0];

describe("runBulk", () => {
    it("chains cursor and expected count over several calls until there is no cursor", async () => {
        const { request, go } = run([
            answer({ published: 100, remaining: 150, next_cursor: SHA(1) }),
            answer({ published: 100, remaining: 50, next_cursor: SHA(2) }),
            answer({ published: 50 }),
        ]);
        const { state, end } = await go();
        expect(end).toEqual({ kind: "finished" });
        expect(request).toHaveBeenCalledTimes(3);
        expect(body(request, 0)).toEqual({
            band: "high",
            filters: { court: "bam" },
            expected_count: 250,
            limit: 100,
        });
        expect(body(request, 1)).toMatchObject({ cursor: SHA(1), expected_count: 150, limit: 100 });
        expect(body(request, 2)).toMatchObject({ cursor: SHA(2), expected_count: 50 });
        expect(state).toMatchObject({ published: 250, done: 250, total: 250, cursor: null });
    });

    it("reports the state after every call", async () => {
        const { onProgress, go } = run([
            answer({ published: 100, remaining: 20, next_cursor: SHA(1) }),
            answer({ published: 20 }),
        ]);
        await go();
        expect(onProgress.mock.calls.map(([s]) => s.done)).toEqual([100, 120]);
    });

    it("collects conflicts and failures without stopping", async () => {
        const { request, go } = run(
            [
                answer({
                    published: 98,
                    conflicts: [ID(1)],
                    failed: [{ extraction_id: ID(2), reason: "source has a newer extraction" }],
                    remaining: 20,
                    next_cursor: SHA(1),
                }),
                answer({ published: 19, conflicts: [ID(3)] }),
            ],
            { total: 120 },
        );
        const { state, end } = await go();
        expect(end.kind).toBe("finished");
        expect(request).toHaveBeenCalledTimes(2);
        expect(state.published).toBe(117);
        expect(state.conflicts).toEqual([ID(1), ID(3)]);
        expect(state.failed).toEqual([{ id: ID(2), reason: "source has a newer extraction" }]);
        expect(state.done).toBe(120);
    });

    it("stops between calls, never in the middle of one", async () => {
        const { request, go } = run(
            [
                answer({ published: 100, remaining: 150, next_cursor: SHA(1) }),
                answer({ published: 100, remaining: 50, next_cursor: SHA(2) }),
            ],
            { stopAfter: 1 },
        );
        const { state, end } = await go();
        expect(end).toEqual({ kind: "stopped" });
        expect(request).toHaveBeenCalledTimes(1);
        expect(state).toMatchObject({ published: 100, cursor: SHA(1), expected: 150 });
    });

    it("halts on bulk_count_changed with the new total, writes nothing and resumes with it", async () => {
        const { request, go } = run([
            answer({ published: 100, remaining: 150, next_cursor: SHA(1) }),
            new ApiFailure("bulk_count_changed", { total: 140, expected: 150 }),
            answer({ published: 100, remaining: 40, next_cursor: SHA(2) }),
            answer({ published: 40 }),
        ]);
        const halted = await go();
        expect(halted.end).toEqual({ kind: "count_changed", total: 140 });
        expect(halted.state).toMatchObject({ published: 100, done: 100, cursor: SHA(1) });

        const resumed = await go(resumeState(halted.state, 140));
        expect(resumed.end.kind).toBe("finished");
        expect(body(request, 2)).toMatchObject({ cursor: SHA(1), expected_count: 140 });
        expect(body(request, 3)).toMatchObject({ cursor: SHA(2), expected_count: 40 });
        expect(resumed.state).toMatchObject({ published: 240, done: 240, total: 240 });
    });

    it("halts on a network error and repeats the same call with the same cursor and count", async () => {
        const { request, go } = run([
            answer({ published: 100, remaining: 50, next_cursor: SHA(1) }),
            new ApiFailure("upstream_unavailable"),
            answer({ published: 50 }),
        ]);
        const halted = await go();
        expect(isRetryable(halted.end)).toBe(true);
        const retried = await go(halted.state);
        expect(retried.end.kind).toBe("finished");
        expect(body(request, 2)).toEqual(body(request, 1));
        expect(body(request, 1)).toMatchObject({ cursor: SHA(1), expected_count: 50 });
    });

    it("treats a call that threw something else as a network error", async () => {
        const request = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
        const { end } = await runBulk({
            request,
            filters: {},
            state: startState(3),
            onProgress: vi.fn(),
            shouldStop: () => false,
        });
        expect(end).toEqual({ kind: "failed", code: "upstream_unavailable", params: {} });
    });

    it("ends on any other error with its code, and does not offer a repeat", async () => {
        const { go } = run([new ApiFailure("bulk_band_not_allowed")]);
        const { end } = await go();
        expect(end).toEqual({ kind: "failed", code: "bulk_band_not_allowed", params: {} });
        expect(isRetryable(end)).toBe(false);
    });
});

describe("resumeState", () => {
    it("covers what is done plus the new count", () => {
        const state = { ...startState(250), done: 100, cursor: SHA(1), expected: 150 };
        expect(resumeState(state, 140)).toMatchObject({
            total: 240,
            expected: 140,
            cursor: SHA(1),
        });
    });
});

describe("bulkFilters", () => {
    it("names the list filters, and the unknown court as the API wants it", () => {
        expect(
            bulkFilters({
                band: "high",
                court: "unknown",
                journalIssue: 61,
                q: "x",
                sort: "score_desc",
                page: 3,
            }),
        ).toEqual({ court: "", reason: undefined, journal_issue: 61, q: "x" });
    });
});

describe("bulkFailureCode", () => {
    it("maps the wording of publish_batch, and leaves unknown reasons alone", () => {
        expect(bulkFailureCode("extraction is no longer in band high")).toBe("band_changed");
        expect(bulkFailureCode("database constraint violated: ix_x")).toBe("constraint_violated");
        expect(bulkFailureCode("something new")).toBeUndefined();
    });

    it("only knows reasons that app.kb still words that way", () => {
        const source = readRepoFile("services/app/app/kb.py");
        for (const reason of [
            "source is no longer in review",
            "source has a newer extraction",
            "extraction has no source",
            "extraction has no source of category 'decision'",
            "extraction has no source in status 'analyzed'",
            "court and court_level are required",
            "extraction is no longer in band ",
            "database constraint violated",
        ]) {
            expect(source, reason).toContain(reason);
            expect(bulkFailureCode(reason)).toBeDefined();
        }
        expect(BULK_FAILURE_CODES).toHaveLength(8);
    });
});
