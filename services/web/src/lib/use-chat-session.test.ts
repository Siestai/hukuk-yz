import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sendMessage } from "./chat-stream";
import type { ChatEvent } from "./chat-types";
import { useChatSession } from "./use-chat-session";

vi.mock("./chat-client", () => ({
    createConversation: vi.fn().mockResolvedValue({ id: "c1" }),
    listConversations: vi.fn().mockResolvedValue([]),
}));
vi.mock("./chat-stream", () => ({ sendMessage: vi.fn() }));

const FACTS = { type: "facts", facts: { title: "Olay", facts: [] } } as unknown as ChatEvent;

/** A stream that yields `events`, then waits until it is aborted (like a fetch body that stalls). */
function stalling(events: ChatEvent[], signals: AbortSignal[]) {
    return async function* (_id: string, _body: unknown, signal?: AbortSignal) {
        if (signal) signals.push(signal);
        for (const event of events) yield event;
        await new Promise<void>((_resolve, reject) =>
            signal?.addEventListener("abort", () =>
                reject(new DOMException("aborted", "AbortError")),
            ),
        );
    };
}

function finishing(events: ChatEvent[]) {
    return async function* () {
        for (const event of events) yield event;
    };
}

beforeEach(() => {
    vi.mocked(sendMessage).mockReset();
    window.history.replaceState(null, "", "/");
});

describe("useChatSession", () => {
    it("aborts the stream on reset and shows nothing of it afterwards", async () => {
        const signals: AbortSignal[] = [];
        vi.mocked(sendMessage).mockImplementation(stalling([FACTS], signals));
        const { result } = renderHook(() => useChatSession(null, []));
        act(() => void result.current.send({ text: "soru" }, "short"));
        await waitFor(() => expect(result.current.live?.facts).not.toBeNull());

        act(() => result.current.reset());
        await act(async () => undefined);

        expect(signals[0]?.aborted).toBe(true);
        expect(result.current.turns).toEqual([]);
        expect(result.current.live).toBeNull();
        expect(result.current.failure).toBeNull();
        expect(result.current.partial).toBeNull();
    });

    it("aborts the stream on unmount", async () => {
        const signals: AbortSignal[] = [];
        vi.mocked(sendMessage).mockImplementation(stalling([], signals));
        const { result, unmount } = renderHook(() => useChatSession(null, []));
        act(() => void result.current.send({ text: "soru" }, "short"));
        await waitFor(() => expect(signals).toHaveLength(1));
        unmount();
        expect(signals[0]?.aborted).toBe(true);
    });

    it("aborts the stream of a run that a new run replaces", async () => {
        const signals: AbortSignal[] = [];
        vi.mocked(sendMessage)
            .mockImplementationOnce(stalling([], signals))
            .mockImplementationOnce(finishing([{ type: "done", turn_id: "t2" } as ChatEvent]));
        const { result } = renderHook(() => useChatSession(null, []));
        act(() => void result.current.send({ text: "bir" }, "short"));
        await waitFor(() => expect(signals).toHaveLength(1));
        await act(async () => result.current.retry());

        expect(signals[0]?.aborted).toBe(true);
        expect(result.current.failure).toBeNull();
    });

    it("keeps the facts of a stream that broke off and retries without a second bubble", async () => {
        vi.mocked(sendMessage)
            .mockImplementationOnce(async function* () {
                yield FACTS;
                throw new ApiFailure("chat_unavailable");
            })
            .mockImplementationOnce(
                finishing([
                    FACTS,
                    { type: "answer", answer: { headline: "x" } } as unknown as ChatEvent,
                    { type: "done", turn_id: "t1" } as ChatEvent,
                ]),
            );
        const { result } = renderHook(() => useChatSession(null, []));
        await act(async () => result.current.send({ text: "soru" }, "short"));

        expect(result.current.failure?.code).toBe("chat_unavailable");
        expect(result.current.partial?.facts).not.toBeNull();
        expect(result.current.turns).toHaveLength(1);

        await act(async () => result.current.retry());

        expect(result.current.failure).toBeNull();
        expect(result.current.partial).toBeNull();
        expect(result.current.turns.map((turn) => turn.role)).toEqual(["user", "assistant"]);
    });

    it("treats a stream that ends without done as a lost connection", async () => {
        vi.mocked(sendMessage).mockImplementation(finishing([FACTS]));
        const { result } = renderHook(() => useChatSession(null, []));
        await act(async () => result.current.send({ text: "soru" }, "short"));
        expect(result.current.failure?.code).toBe("upstream_unavailable");
        expect(result.current.partial?.facts).not.toBeNull();
    });

    it("shows the error of an error event followed by done, and stores no turn", async () => {
        vi.mocked(sendMessage).mockImplementation(
            finishing([
                { type: "error", code: "chat_unavailable", params: {} } as ChatEvent,
                { type: "done" } as ChatEvent,
            ]),
        );
        const { result } = renderHook(() => useChatSession(null, []));
        await act(async () => result.current.send({ text: "soru" }, "short"));
        expect(result.current.failure?.code).toBe("chat_unavailable");
        expect(result.current.turns.map((turn) => turn.role)).toEqual(["user"]);
    });
});
