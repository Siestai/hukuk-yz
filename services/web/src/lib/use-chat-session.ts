"use client";

import { createApiClient } from "@hukuk/web-core/api/client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { useCallback, useMemo, useRef, useState } from "react";

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
        redacted_names: 0,
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
    const lastBody = useRef<MessageRequest | null>(null);
    const busy = live !== null;

    const run = useCallback(
        async (body: MessageRequest, showSent: boolean) => {
            lastBody.current = body;
            setFailure(null);
            if (showSent) setTurns((previous) => [...previous, sentTurn(body)]);
            let current = emptyLive;
            setLive(current);
            try {
                let id = conversationId;
                if (!id) {
                    id = (await createConversation(api)).id;
                    setConversationId(id);
                    window.history.replaceState(null, "", `/konusmalar/${id}`);
                }
                for await (const event of sendMessage(id, body)) {
                    current = applyEvent(current, event);
                    setLive(current);
                }
                const turn = toTurn(current, new Date().toISOString());
                if (turn) setTurns((previous) => [...previous, turn]);
                if (current.error) setFailure(current.error);
                else if (!current.finished)
                    setFailure({ code: "upstream_unavailable", params: {} });
            } catch (error) {
                setFailure(
                    error instanceof ApiFailure
                        ? { code: error.code, params: error.params }
                        : { code: "upstream_unavailable", params: {} },
                );
            }
            setLive(null);
            void listConversations(api).then(setConversations, () => undefined);
        },
        [api, conversationId],
    );

    const reset = useCallback(() => {
        setConversationId(null);
        setTurns([]);
        setLive(null);
        setFailure(null);
        lastBody.current = null;
    }, []);

    return {
        reset,
        conversations,
        conversationId,
        turns,
        live,
        failure,
        busy,
        /** Sends a question, the answers to the open questions, or the skip. */
        send: (reply: Reply, mode: ChatMode) => run({ skip: false, ...reply, mode }, true),
        /** Sends the last request again, without a second bubble. */
        retry: () => (lastBody.current ? run(lastBody.current, false) : undefined),
    };
}
