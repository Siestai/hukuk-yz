"use client";

import { useRef, useState } from "react";

import { createApiClient } from "@/lib/api/client";
import { postBulkApprove } from "@/lib/api/review-client";
import {
    isRetryable,
    resumeState,
    runBulk,
    startState,
    type BulkEnd,
    type BulkFilters,
    type BulkState,
} from "@/lib/bulk-approve";

/** Where the dialog is: asking, calling the API, waiting for the user after a halt, or reporting. */
export type BulkPhase = "confirm" | "running" | "halted" | "report";

/**
 * The run of a bulk approval as the dialog sees it; the loop itself is `runBulk`. `filters` and
 * `total` are read when `start` is called; later changes of them do not reach the run.
 */
export function useBulkApprove({ filters, total }: { filters: BulkFilters; total: number }) {
    const api = useRef(createApiClient());
    // What the run covers is fixed when it starts: the page may change its props under the dialog.
    const started = useRef({ filters, total });
    const stopRequested = useRef(false);
    const [phase, setPhase] = useState<BulkPhase>("confirm");
    const [state, setState] = useState(() => startState(total));
    const [end, setEnd] = useState<BulkEnd | null>(null);
    const [stopping, setStopping] = useState(false);

    async function run(from: BulkState) {
        stopRequested.current = false;
        setStopping(false);
        setEnd(null);
        setState(from);
        setPhase("running");
        const result = await runBulk({
            request: (body) => postBulkApprove(api.current, body),
            filters: started.current.filters,
            state: from,
            onProgress: setState,
            shouldStop: () => stopRequested.current,
        });
        setState(result.state);
        setEnd(result.end);
        // The user waits only where something can be done about it: a repeat or a new count.
        setPhase(
            result.end.kind === "count_changed" || isRetryable(result.end) ? "halted" : "report",
        );
    }

    return {
        phase,
        state,
        end,
        stopping,
        start: () => {
            started.current = { filters, total };
            return run(startState(total));
        },
        /** Repeats the call that failed, with the same cursor and expected count. */
        retry: () => run(state),
        /** Goes on from the same cursor over the `expected` records the API now counts. */
        resume: (expected: number) => run(resumeState(state, expected)),
        /** Takes effect once the call in flight has answered. */
        stop: () => {
            stopRequested.current = true;
            setStopping(true);
        },
        showReport: () => setPhase("report"),
    };
}
