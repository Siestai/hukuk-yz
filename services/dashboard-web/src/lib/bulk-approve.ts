import { ApiFailure } from "@/lib/api/review-client";
import type { components } from "@/lib/api/schema";
import { apiQuery, type QueueParams } from "@/lib/queue-params";

export type BulkRequest = components["schemas"]["BulkApproveRequest"];
export type BulkResponse = components["schemas"]["BulkApproveResponse"];
export type BulkFilters = NonNullable<BulkRequest["filters"]>;

/** How many records one call may take; the API's ceiling. */
export const BULK_LIMIT = 100;

/** The filters of the list as the bulk body names them (`band` apart). */
export function bulkFilters(params: QueueParams): BulkFilters {
    const { court, reason, journal_issue, q } = apiQuery(params);
    return { court, reason, journal_issue, q };
}

/**
 * What the run has done so far, which is also where it goes on: the next call takes `cursor`
 * and `expected` (the records the API will count after the cursor). `total` is what the run
 * covers (done plus expected); it changes only when the queue did.
 */
export type BulkState = {
    published: number;
    conflicts: string[];
    failed: { id: string; reason: string }[];
    done: number;
    total: number;
    cursor: string | null;
    expected: number;
};

export function startState(total: number): BulkState {
    return {
        published: 0,
        conflicts: [],
        failed: [],
        done: 0,
        total,
        cursor: null,
        expected: total,
    };
}

/** The same run over a queue that now holds `expected` records after the cursor. */
export function resumeState(state: BulkState, expected: number): BulkState {
    return { ...state, expected, total: state.done + expected };
}

/** Why a run ended: it went through, the user stopped it, the queue changed, or a call failed. */
export type BulkEnd =
    | { kind: "finished" }
    | { kind: "stopped" }
    | { kind: "count_changed"; total: number }
    | { kind: "failed"; code: string | undefined; params: Record<string, unknown> };

/** A call that did not reach the API may be repeated as it was; anything else the API refused. */
export function isRetryable(end: BulkEnd): boolean {
    return end.kind === "failed" && end.code === "upstream_unavailable";
}

type Run = {
    /** One call of `POST /review/decisions/bulk-approve`; it throws `ApiFailure` when refused. */
    request: (body: BulkRequest) => Promise<BulkResponse>;
    filters: BulkFilters;
    state: BulkState;
    onProgress: (state: BulkState) => void;
    /** Asked between calls only: a call that has gone out is never abandoned. */
    shouldStop: () => boolean;
};

/**
 * Calls the API until it has no cursor left, as its contract says: each call takes the cursor and
 * the remaining count of the one before. Conflicts and failures stay in the queue and do not stop
 * the run. Nothing is counted here; every number comes from the answers.
 */
export async function runBulk({
    request,
    filters,
    state,
    onProgress,
    shouldStop,
}: Run): Promise<{ state: BulkState; end: BulkEnd }> {
    let current = state;
    for (;;) {
        if (shouldStop()) return { state: current, end: { kind: "stopped" } };
        let answer: BulkResponse;
        try {
            answer = await request({
                band: "high",
                filters,
                expected_count: current.expected,
                limit: BULK_LIMIT,
                ...(current.cursor ? { cursor: current.cursor } : {}),
            });
        } catch (error) {
            const failure =
                error instanceof ApiFailure ? error : new ApiFailure("upstream_unavailable");
            const total = failure.params.total;
            if (failure.code === "bulk_count_changed" && typeof total === "number") {
                return { state: current, end: { kind: "count_changed", total } };
            }
            return {
                state: current,
                end: { kind: "failed", code: failure.code, params: failure.params },
            };
        }
        const handled = answer.published + answer.conflicts.length + answer.failed.length;
        current = {
            ...current,
            published: current.published + answer.published,
            conflicts: [...current.conflicts, ...answer.conflicts],
            failed: [
                ...current.failed,
                ...answer.failed.map((f) => ({ id: f.extraction_id, reason: f.reason })),
            ],
            done: current.done + handled,
            cursor: answer.next_cursor,
            expected: answer.remaining,
        };
        onProgress(current);
        if (answer.next_cursor === null) return { state: current, end: { kind: "finished" } };
    }
}

/**
 * `publish_batch` words its refusals in English (`app.kb`); these are the ones it can give, as
 * the keys of `enums.bulkFailure`. A reason not listed is shown as it came.
 */
const FAILURE_CODES: Record<string, string> = {
    "source is no longer in review": "source_not_in_review",
    "source has a newer extraction": "newer_extraction",
    "extraction has no source": "no_source",
    "extraction has no source of category 'decision'": "no_decision_source",
    "extraction has no source in status 'analyzed'": "source_not_analyzed",
    "court and court_level are required": "court_required",
};
const FAILURE_PREFIXES: [prefix: string, code: string][] = [
    ["extraction is no longer in band ", "band_changed"],
    ["database constraint violated", "constraint_violated"],
];

export const BULK_FAILURE_CODES = [
    ...Object.values(FAILURE_CODES),
    ...FAILURE_PREFIXES.map(([, code]) => code),
];

/** The `enums.bulkFailure` key of a reason, or undefined when it is not one of the known. */
export function bulkFailureCode(reason: string): string | undefined {
    return (
        FAILURE_CODES[reason] ?? FAILURE_PREFIXES.find(([prefix]) => reason.startsWith(prefix))?.[1]
    );
}
