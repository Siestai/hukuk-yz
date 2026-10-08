import {
    changeQueueParams,
    detailHref,
    parseQueueParams,
    queueHref,
    serializeQueueParams,
    statusOf,
    tabParams,
    type Flash,
    type Notice,
    type QueueParams,
    type QueueStatus,
    type RawParams,
} from "./queue-params";
import {
    changeStatuteParams,
    parseStatuteParams,
    serializeStatuteParams,
    statuteDetailHref,
    statuteListHref,
    statuteTabParams,
    type StatuteQueueParams,
} from "./statute-queue-params";

/**
 * The two review queues, decisions and statute articles, share their components (tabs, search,
 * pagination, bulk approval, the review session). They work on either state through these
 * functions; `kind` of the statute state is what tells them apart.
 */
export type QueueState = QueueParams | StatuteQueueParams;
export type QueueKind = "decision" | "statute";

export function isStatuteState(state: QueueState): state is StatuteQueueParams {
    return "kind" in state && state.kind === "statute";
}

export function parseState(kind: QueueKind, raw: RawParams): QueueState {
    return kind === "statute" ? parseStatuteParams(raw) : parseQueueParams(raw);
}

export function stateStatus(state: QueueState): QueueStatus {
    return isStatuteState(state) ? (state.status ?? "pending") : statusOf(state);
}

/** The URL query of a state, as a comparable string. */
export function stateKey(state: QueueState): string {
    return (
        isStatuteState(state) ? serializeStatuteParams(state) : serializeQueueParams(state)
    ).toString();
}

export function stateHref(state: QueueState, notice?: Notice): string {
    return isStatuteState(state) ? statuteListHref(state, notice) : queueHref(state, notice);
}

export function stateDetailHref(
    extractionId: string,
    state: QueueState,
    extra: { pos?: number; flash?: Flash } = {},
): string {
    return isStatuteState(state)
        ? statuteDetailHref(extractionId, state, extra)
        : detailHref(extractionId, state, extra);
}

/** The state of a status tab (the filters stay, the first page opens). */
export function stateTab<P extends QueueState>(state: P, status: QueueStatus): P {
    return (
        isStatuteState(state)
            ? statuteTabParams(state, status)
            : tabParams(state as QueueParams, status)
    ) as P;
}

/** Applies a change; any change that does not name a page goes back to page 1. */
export function changeState<P extends QueueState>(state: P, change: Partial<P>): P {
    return (
        isStatuteState(state)
            ? changeStatuteParams(state, change as Partial<StatuteQueueParams>)
            : changeQueueParams(state as QueueParams, change as Partial<QueueParams>)
    ) as P;
}
