"use client";

import { createApiClient } from "@hukuk/web-core/api/client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { createConversation, listConversations } from "./chat-client";
import { applyEvent, emptyLive, toTurn, type LiveTurn } from "./chat-state";
import { sendMessage } from "./chat-stream";
import type {
    ChatMode,
    Conversation,
    ConversationDetail,
    MessageRequest,
    Reply,
    Turn,
} from "./chat-types";

export type Failure = { code: string | undefined; params: Record<string, unknown> };

/** The user turn as it is shown before the server has answered. */
function sentTurn(body: MessageRequest): Turn {
    return {
        id: crypto.randomUUID(),
        role: "user",
        created_at: new Date().toISOString(),
        text: body.text ?? null,
        clarification_answers: body.clarification_answers ?? null,
        skipped: body.skip ?? false,
    };
}

/**
 * The state of one conversation on screen: its turns, the assistant turn that is streaming, and
 * what went wrong. The first question creates the conversation and puts its address in the URL.
 */
export function useChatSession(initial: ConversationDetail | null, initialList: Conversation[]) {
    const api = useMemo(() => createApiClient(), []);
    const [conversationId, setConversationId] = useState<string | null>(initial?.id ?? null);
    const [turns, setTurns] = useState<Turn[]>(initial?.turns ?? []);
    const [conversations, setConversations] = useState(initialList);
    const [live, setLive] = useState<LiveTurn | null>(null);
    const [failure, setFailure] = useState<Failure | null>(null);
    // What a stream that broke off had already delivered; shown above the error, gone on the next run.
    const [partial, setPartial] = useState<LiveTurn | null>(null);
    const lastBody = useRef<MessageRequest | null>(null);
    const stream = useRef<AbortController | null>(null);
    const busy = live !== null;

    const run = useCallback(
        async (body: MessageRequest, showSent: boolean) => {
            stream.current?.abort();
            const controller = new AbortController();
            stream.current = controller;
            lastBody.current = body;
            setFailure(null);
            setPartial(null);
            if (showSent) setTurns((previous) => [...previous, sentTurn(body)]);
            let current = emptyLive;
            setLive(current);
            try {
                let id = conversationId;
                if (!id) {
                    id = (await createConversation(api)).id;
                    if (controller.signal.aborted) return;
                    setConversationId(id);
                    window.history.replaceState(null, "", `/konusmalar/${id}`);
                }
                for await (const event of sendMessage(id, body, controller.signal)) {
                    if (controller.signal.aborted) return;
                    current = applyEvent(current, event);
                    setLive(current);
                }
                if (controller.signal.aborted) return;
                const turn = toTurn(current, new Date().toISOString());
                if (turn) setTurns((previous) => [...previous, turn]);
                if (current.error) setFailure(current.error);
                else if (!current.finished)
                    setFailure({ code: "upstream_unavailable", params: {} });
                if (!turn && (current.facts || current.clarification)) setPartial(current);
            } catch (error) {
                // A stream we aborted belongs to a screen that is gone; it must not write to the new one.
                if (controller.signal.aborted) return;
                if (current.facts || current.clarification) setPartial(current);
                setFailure(
                    error instanceof ApiFailure
                        ? { code: error.code, params: error.params }
                        : { code: "upstream_unavailable", params: {} },
                );
            }
            setLive(null);
            void listConversations(api).then(
                (items) => {
                    if (!controller.signal.aborted) setConversations(items);
                },
                () => undefined,
            );
        },
        [api, conversationId],
    );

    const reset = useCallback(() => {
        stream.current?.abort();
        setConversationId(null);
        setTurns([]);
        setLive(null);
        setFailure(null);
        setPartial(null);
        lastBody.current = null;
    }, []);

    useEffect(() => () => stream.current?.abort(), []);

    return {
        reset,
        conversations,
        conversationId,
        turns,
        live,
        failure,
        partial,
        busy,
        /** Sends a question, the answers to the open questions, or the skip. */
        send: (reply: Reply, mode: ChatMode) => run({ skip: false, ...reply, mode }, true),
        /** Sends the last request again, without a second bubble. */
        retry: () => (lastBody.current ? run(lastBody.current, false) : undefined),
    };
}
