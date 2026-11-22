import { describe, expect, it } from "vitest";

import { applyEvent, emptyLive, toTurn } from "./chat-state";
import { sourceGap } from "@/test/answer-fixture";
import type { ChatEvent } from "./chat-types";

const facts = { facts: [] } as unknown as Extract<ChatEvent, { type: "facts" }>["facts"];

function play(events: ChatEvent[]) {
    return events.reduce(applyEvent, emptyLive);
}

describe("applyEvent", () => {
    it("shows the label of a step until something else arrives", () => {
        const live = play([{ type: "step", node: "read", label: "Kaynaklar okunuyor..." }]);
        expect(live.label).toBe("Kaynaklar okunuyor...");
        expect(applyEvent(live, { type: "facts", facts }).facts).toBe(facts);
        expect(applyEvent(live, { type: "done" }).label).toBeNull();
    });

    it("keeps the error code and its parameters", () => {
        const live = play([
            { type: "error", code: "chat_unavailable", params: { n: 2 }, retryable: false },
        ]);
        expect(live.error).toEqual({
            code: "chat_unavailable",
            params: { n: 2 },
            retryable: false,
            source_gap: null,
        });
    });
});

describe("toTurn", () => {
    it("stores a finished stream under the id of the turn", () => {
        const live = play([
            { type: "facts", facts },
            { type: "done", turn_id: "t1", trace_id: "tr1" },
        ]);
        expect(toTurn(live, "2026-10-28T10:00:00Z")).toMatchObject({
            id: "t1",
            role: "assistant",
            trace_id: "tr1",
            facts,
        });
    });

    it("stores an error the server kept as a turn, with what was missing", () => {
        const live = play([
            { type: "facts", facts },
            {
                type: "error",
                code: "answer_not_verified",
                params: {},
                retryable: false,
                source_gap: sourceGap,
            },
            { type: "done", turn_id: "t1" },
        ]);
        expect(toTurn(live, "x")).toMatchObject({
            id: "t1",
            facts,
            error: { type: "error", code: "answer_not_verified", source_gap: sourceGap },
        });
    });

    it("gives nothing for an open stream, an unsaved error or an empty stream", () => {
        expect(toTurn(play([{ type: "facts", facts }]), "x")).toBeNull();
        expect(
            toTurn(
                play([
                    { type: "error", code: "internal_error", params: {}, retryable: false },
                    { type: "done", turn_id: null },
                ]),
                "x",
            ),
        ).toBeNull();
        expect(toTurn(play([{ type: "done", turn_id: "t1" }]), "x")).toBeNull();
    });
});
