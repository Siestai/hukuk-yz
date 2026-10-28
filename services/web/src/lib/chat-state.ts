import type { Answer, CaseFacts, ChatEvent, Clarification, Turn } from "./chat-types";

/** The assistant turn while its stream is open. */
export type LiveTurn = {
    label: string | null;
    facts: CaseFacts | null;
    clarification: Clarification | null;
    answer: Answer | null;
    error: { code: string; params: Record<string, string | number> } | null;
    /** Set by the `done` event; null while the stream is open or when it ended in an error. */
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
                error: { code: event.code, params: event.params ?? {} },
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

/** The stored form of a finished stream; null when it ended in an error or carries nothing. */
export function toTurn(live: LiveTurn, createdAt: string): Turn | null {
    if (!live.finished || live.error || !live.turnId) return null;
    if (!live.facts && !live.clarification && !live.answer) return null;
    return {
        id: live.turnId,
        role: "assistant",
        created_at: createdAt,
        skipped: false,
        facts: live.facts,
        clarification: live.clarification,
        answer: live.answer,
        trace_id: live.traceId,
    };
}
