import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatEvent } from "./chat-types";
import { readEvents, sendMessage } from "./chat-stream";

function body(...chunks: string[]) {
    const encoder = new TextEncoder();
    return new ReadableStream<Uint8Array>({
        start(controller) {
            for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
            controller.close();
        },
    });
}

async function collect(events: AsyncGenerator<ChatEvent>) {
    const all: ChatEvent[] = [];
    for await (const event of events) all.push(event);
    return all;
}

afterEach(() => vi.unstubAllGlobals());

describe("readEvents", () => {
    it("joins an event split across chunks and skips comments", async () => {
        const events = await collect(
            readEvents(
                body(
                    ': ping\n\ndata: {"type":"step","node":"a",',
                    '"label":"Okunuyor"}\r\n\r\ndata: {"type":"done"}',
                ),
            ),
        );
        expect(events).toEqual([{ type: "step", node: "a", label: "Okunuyor" }, { type: "done" }]);
    });
});

describe("sendMessage", () => {
    it("throws the code of an error response", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(JSON.stringify({ detail: { code: "chat_unavailable" } }), {
                    status: 503,
                }),
            ),
        );
        await expect(
            collect(sendMessage("c1", { text: "x", mode: "short", skip: false })),
        ).rejects.toBeInstanceOf(ApiFailure);
    });

    it("reports a lost connection as upstream_unavailable", async () => {
        vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
        await expect(
            collect(sendMessage("c1", { text: "x", mode: "short", skip: false })),
        ).rejects.toMatchObject({
            code: "upstream_unavailable",
        });
    });
});
