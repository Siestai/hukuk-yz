import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { apiError } from "@hukuk/web-core/api/errors";

import type { ChatEvent, MessageRequest } from "./chat-types";

/** The events of an SSE body, in order; a block without `data:` lines (a comment) is skipped. */
export async function* readEvents(body: ReadableStream<Uint8Array>): AsyncGenerator<ChatEvent> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const parse = (block: string): ChatEvent | null => {
        const data = block
            .split("\n")
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).replace(/^ /, ""))
            .join("\n");
        return data ? (JSON.parse(data) as ChatEvent) : null;
    };
    try {
        for (;;) {
            const { done, value } = await reader.read();
            buffer = (buffer + decoder.decode(value, { stream: !done })).replaceAll("\r\n", "\n");
            let end = buffer.indexOf("\n\n");
            while (end >= 0) {
                const event = parse(buffer.slice(0, end));
                buffer = buffer.slice(end + 2);
                if (event) yield event;
                end = buffer.indexOf("\n\n");
            }
            if (done) break;
        }
        const rest = parse(buffer);
        if (rest) yield rest;
    } finally {
        await reader.cancel().catch(() => undefined);
    }
}

/** Posts a message and yields the answer's events; an error status throws an `ApiFailure`. */
export async function* sendMessage(
    conversationId: string,
    body: MessageRequest,
    signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
    const response = await fetch(`/api/chat/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "content-type": "application/json", accept: "text/event-stream" },
        body: JSON.stringify(body),
        credentials: "same-origin",
        signal,
    }).catch((error: unknown) => {
        if (signal?.aborted) throw error;
        throw new ApiFailure("upstream_unavailable");
    });
    if (!response.ok || !response.body) {
        const { code, params } = apiError(await response.json().catch(() => null));
        throw new ApiFailure(code ?? "upstream_unavailable", params);
    }
    yield* readEvents(response.body);
}
