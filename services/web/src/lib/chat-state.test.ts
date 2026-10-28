import { describe, expect, it } from "vitest";

import { applyEvent, emptyLive, toTurn } from "./chat-state";
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
        const live = play([{ type: "error", code: "chat_unavailable", params: { n: 2 } }]);
        expect(live.error).toEqual({ code: "chat_unavailable", params: { n: 2 } });
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

    it("gives nothing for an open stream, an error or an empty stream", () => {
        expect(toTurn(play([{ type: "facts", facts }]), "x")).toBeNull();
        expect(
            toTurn(
                play([
                    { type: "error", code: "internal_error", params: {} },
                    { type: "done", turn_id: "t1" },
                ]),
                "x",
            ),
        ).toBeNull();
        expect(toTurn(play([{ type: "done", turn_id: "t1" }]), "x")).toBeNull();
    });
});
