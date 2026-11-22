import type {
    Answer,
    CaseFacts,
    ChatEvent,
    Clarification,
    ErrorEvent,
    SourceGap,
    Turn,
} from "./chat-types";

/** The assistant turn while its stream is open. */
export type LiveTurn = {
    label: string | null;
    facts: CaseFacts | null;
    clarification: Clarification | null;
    answer: Answer | null;
    error: {
        code: ErrorEvent["code"];
        params: Record<string, string | number>;
        retryable: boolean;
        source_gap: SourceGap | null;
    } | null;
    /** Set by the `done` event; null while the stream is open or when no turn was saved. */
    turnId: string | null;
    traceId: string | null;
    finished: boolean;
};

export const emptyLive: LiveTurn = {
    label: null,
    facts: null,
    clarification: null,
    answer: null,
    error: null,
    turnId: null,
    traceId: null,
    finished: false,
};

export function applyEvent(live: LiveTurn, event: ChatEvent): LiveTurn {
    switch (event.type) {
        case "step":
            return { ...live, label: event.label };
        case "facts":
            return { ...live, facts: event.facts };
        case "clarification":
            return { ...live, clarification: event.clarification, label: null };
        case "answer":
            return { ...live, answer: event.answer, label: null };
        case "error":
            return {
                ...live,
                error: {
                    code: event.code,
                    params: event.params ?? {},
                    retryable: event.retryable ?? false,
                    source_gap: event.source_gap ?? null,
                },
                label: null,
            };
        case "done":
            return {
                ...live,
                turnId: event.turn_id ?? null,
                traceId: event.trace_id ?? null,
                label: null,
                finished: true,
            };
    }
}

/**
 * The stored form of a finished stream; null when no turn was saved or it carries nothing. An
 * error the server saved as a turn is kept, so that it can get feedback.
 */
export function toTurn(live: LiveTurn, createdAt: string): Turn | null {
    if (!live.finished || !live.turnId) return null;
    if (!live.facts && !live.clarification && !live.answer && !live.error) return null;
    const error = live.error ? { type: "error" as const, ...live.error } : null;
    return {
        id: live.turnId,
        role: "assistant",
        created_at: createdAt,
        skipped: false,
        facts: live.facts,
        clarification: live.clarification,
        answer: live.answer,
        error,
        trace_id: live.traceId,
    };
}
