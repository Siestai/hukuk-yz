import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { sendMessage } from "./chat-stream";
import type { ChatEvent, ConversationDetail, Reply } from "./chat-types";
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

    it("ignores a late event from a cancelled stream", async () => {
        let release: () => void = () => undefined;
        vi.mocked(sendMessage).mockImplementation(async function* () {
            await new Promise<void>((resolve) => {
                release = resolve;
            });
            yield FACTS;
            yield { type: "done", turn_id: "old" } as ChatEvent;
        });
        const { result } = renderHook(() => useChatSession(null, []));
        act(() => void result.current.send({ text: "soru" }, "short"));
        await waitFor(() => expect(sendMessage).toHaveBeenCalledOnce());
        act(() => result.current.reset());
        await act(async () => release());
        expect(result.current.turns).toEqual([]);
        expect(result.current.live).toBeNull();
        expect(result.current.conversationId).toBeNull();
    });

    it("resends a failed clarification reply without adding another user turn", async () => {
        const reply = {
            clarification_answers: [{ question_id: "q1", value: "30+", unknown: false }],
        };
        vi.mocked(sendMessage)
            .mockImplementationOnce(
                finishing([
                    { type: "error", code: "internal_error", params: {} } as ChatEvent,
                    { type: "done" } as ChatEvent,
                ]),
            )
            .mockImplementationOnce(
                finishing([
                    { type: "answer", answer: { headline: "x" } } as unknown as ChatEvent,
                    { type: "done", turn_id: "t1" } as ChatEvent,
                ]),
            );
        const initial = {
            id: "c1",
            turns: [{ id: "clarify", role: "assistant", clarification: { questions: [] } }],
        } as unknown as ConversationDetail;
        const { result } = renderHook(() => useChatSession(initial, []));
        await act(async () => result.current.send(reply, "short"));
        expect(result.current.failure?.code).toBe("internal_error");
        await act(async () => result.current.retry());
        expect(result.current.failure).toBeNull();
        expect(result.current.turns.filter((turn) => turn.role === "user")).toHaveLength(1);
        expect(vi.mocked(sendMessage).mock.calls[1]?.[1]).toEqual({
            ...reply,
            skip: false,
            mode: "short",
        });
    });

    it.each([
        { reload: false, reply: { skip: true } },
        { reload: true, reply: { skip: true } },
        {
            reload: false,
            reply: { clarification_answers: [{ question_id: "q1", value: "30+", unknown: false }] },
        },
        {
            reload: true,
            reply: { clarification_answers: [{ question_id: "q1", value: "30+", unknown: false }] },
        },
    ] satisfies { reload: boolean; reply: Reply }[])(
        "restarts accepted interrupted clarification: %j",
        async ({ reload, reply }) => {
            const initial = {
                id: "c1",
                turns: [
                    { id: "question", role: "user", text: "ilk soru" },
                    { id: "clarify", role: "assistant", clarification: { questions: [] } },
                    ...(reload
                        ? [
                              {
                                  id: "reply",
                                  role: "user",
                                  skipped: reply.skip ?? false,
                                  clarification_answers: reply.clarification_answers,
                              },
                          ]
                        : []),
                ],
            } as unknown as ConversationDetail;
            vi.mocked(sendMessage).mockImplementation(async function* (_id, body) {
                // Real fixture contract: accepted replies leave no pending clarification.
                if (!body.text) {
                    if (reload) throw new ApiFailure("clarification_not_pending");
                    yield { type: "step", node: "understand", label: "Soru okunuyor" };
                    throw new TypeError("connection lost after acceptance");
                }
                yield {
                    type: "clarification",
                    clarification: { questions: [], index: 0, total: 0 },
                };
                yield { type: "done", turn_id: "restarted" } as ChatEvent;
            });
            const { result } = renderHook(() => useChatSession(initial, []));
            if (!reload) await act(async () => result.current.send(reply, "short"));
            expect(result.current.failure).not.toBeNull();
            expect(result.current.failure).toMatchObject({ restart: true });
            await act(async () => result.current.retry());
            expect(result.current.failure).toBeNull();
            expect(result.current.turns.at(-1)?.id).toBe("restarted");
            expect(result.current.turns.filter((turn) => turn.role === "user")).toHaveLength(2);
            expect(vi.mocked(sendMessage).mock.calls.at(-1)?.[1]).toMatchObject({
                text: "ilk soru",
                skip: false,
            });
        },
    );

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

it.each([
    { skip: true },
    { clarification_answers: [{ question_id: "q1", value: "30+", unknown: false }] },
])(
    "retries durable delivery after reload with selected facts and its original identity: %j",
    async (reply) => {
        const pending = {
            ...reply,
            mode: "detailed",
            request_id: "a5044bdb-ed04-4ccc-9957-a10673fe0648",
        };
        const initial = {
            id: "c1",
            durable_delivery: true,
            pending_request: pending,
            turns: [
                { id: "question", role: "user", text: "original" },
                { id: "clarify", role: "assistant", clarification: { questions: [] } },
                {
                    id: "reply",
                    role: "user",
                    skipped: "skip" in reply,
                    clarification_answers:
                        "clarification_answers" in reply ? reply.clarification_answers : null,
                },
            ],
        } as unknown as ConversationDetail;
        vi.mocked(sendMessage).mockImplementation(
            finishing([
                { type: "answer", answer: { headline: "x" } } as unknown as ChatEvent,
                { type: "done", turn_id: "saved" } as ChatEvent,
            ]),
        );
        const { result } = renderHook(() => useChatSession(initial, []));
        expect(result.current.failure?.restart).toBe(false);
        await act(async () => result.current.retry());
        expect(vi.mocked(sendMessage).mock.calls[0]?.[1]).toEqual(pending);
        expect(result.current.turns.filter((t) => t.role === "user")).toHaveLength(2);
        expect(result.current.turns.at(-1)?.id).toBe("saved");
    },
);

it.each(
    ["answer_not_verified", "internal_error", "chat_unavailable", "upstream_unavailable"].flatMap(
        (code) => [false, true].map((reload) => ({ code, reload })),
    ),
)(
    "preserves completed durable error without retry: $code, reload=$reload",
    async ({ code, reload }) => {
        const error = {
            type: "error",
            code,
            params: { reason: "no_verified_rows", count: 0 },
        } as const;
        const initial = {
            id: "c1",
            durable_delivery: true,
            pending_request: null,
            terminal_error: reload ? error : null,
            turns: reload ? [{ id: "u1", role: "user", text: "soru" }] : [],
        } as unknown as ConversationDetail;
        vi.mocked(sendMessage).mockImplementation(
            finishing([error as unknown as ChatEvent, { type: "done", turn_id: null }]),
        );
        const { result } = renderHook(() => useChatSession(initial, []));
        if (!reload) await act(async () => result.current.send({ text: "soru" }, "short"));
        expect(result.current.failure).toMatchObject({
            code: error.code,
            params: error.params,
            retryable: false,
        });
        expect(result.current.turns.map((t) => t.role)).toEqual(["user"]);
        expect(result.current.failure?.restart).toBe(false);
        const calls = vi.mocked(sendMessage).mock.calls.length;
        expect(calls).toBe(reload ? 0 : 1);
        await act(async () => result.current.retry());
        expect(sendMessage).toHaveBeenCalledTimes(calls);
        await act(async () => result.current.send({ text: "yeni soru" }, "short"));
        expect(sendMessage).toHaveBeenCalledTimes(calls + 1);
        const newBody = vi.mocked(sendMessage).mock.calls.at(-1)?.[1];
        expect(newBody).toMatchObject({ text: "yeni soru", mode: "short" });
        expect(newBody?.request_id).toEqual(expect.any(String));
        if (!reload)
            expect(newBody?.request_id).not.toBe(
                vi.mocked(sendMessage).mock.calls[0]?.[1].request_id,
            );
    },
);

it.each([false, true])(
    "resumes interrupted durable error with the same request id, done=%s",
    async (done) => {
        const initial = {
            id: "c1",
            durable_delivery: true,
            turns: [],
        } as unknown as ConversationDetail;
        vi.mocked(sendMessage)
            .mockImplementationOnce(
                finishing([
                    { type: "error", code: "internal_error", params: {}, retryable: false },
                    // A missing done is an interrupted delivery, even after an error event.
                    ...(done ? [{ type: "done", turn_id: null } as ChatEvent] : []),
                ]),
            )
            .mockImplementationOnce(finishing([{ type: "done", turn_id: null }]));
        const { result } = renderHook(() => useChatSession(initial, []));
        await act(async () => result.current.send({ text: "soru" }, "short"));
        const original = vi.mocked(sendMessage).mock.calls[0]?.[1];
        expect(original?.request_id).toEqual(expect.any(String));
        expect(result.current.failure?.retryable).toBe(!done);
        await act(async () => result.current.retry());
        expect(sendMessage).toHaveBeenCalledTimes(done ? 1 : 2);
        if (!done) expect(vi.mocked(sendMessage).mock.calls[1]?.[1]).toEqual(original);
        expect(result.current.turns.map((turn) => turn.role)).toEqual(["user"]);
    },
);

it("offers retry with the same request id after a transient bridge error the server marked retryable", async () => {
    const initial = {
        id: "c1",
        durable_delivery: true,
        turns: [],
    } as unknown as ConversationDetail;
    vi.mocked(sendMessage)
        .mockImplementationOnce(
            finishing([
                { type: "error", code: "chat_unavailable", params: {}, retryable: true },
                { type: "done", turn_id: null } as ChatEvent,
            ]),
        )
        .mockImplementationOnce(finishing([{ type: "done", turn_id: null }]));
    const { result } = renderHook(() => useChatSession(initial, []));
    await act(async () => result.current.send({ text: "soru" }, "short"));
    const original = vi.mocked(sendMessage).mock.calls[0]?.[1];
    expect(result.current.failure).toMatchObject({ code: "chat_unavailable", retryable: true });
    await act(async () => result.current.retry());
    expect(sendMessage).toHaveBeenCalledTimes(2);
    expect(vi.mocked(sendMessage).mock.calls[1]?.[1]).toEqual(original);
});
