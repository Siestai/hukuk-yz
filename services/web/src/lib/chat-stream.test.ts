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

describe("readEvents with a broken stream", () => {
    it("yields an error event and the done event after it", async () => {
        const events = await collect(
            readEvents(
                body(
                    'data: {"type":"error","code":"chat_unavailable","params":{}}\n\n',
                    'data: {"type":"done"}\n\n',
                ),
            ),
        );
        expect(events.map((event) => event.type)).toEqual(["error", "done"]);
    });

    it("ends without a done event when the body stops early", async () => {
        const events = await collect(
            readEvents(body('data: {"type":"step","node":"a","label":"x"}\n\n')),
        );
        expect(events.map((event) => event.type)).toEqual(["step"]);
    });

    it("keeps the event of a final block without the blank line", async () => {
        const events = await collect(readEvents(body('data: {"type":"done"}')));
        expect(events).toEqual([{ type: "done" }]);
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

    it("lets an abort through as it is, not as a lost connection", async () => {
        const controller = new AbortController();
        controller.abort();
        vi.stubGlobal(
            "fetch",
            vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")),
        );
        await expect(
            collect(
                sendMessage("c1", { text: "x", mode: "short", skip: false }, controller.signal),
            ),
        ).rejects.toMatchObject({ name: "AbortError" });
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
