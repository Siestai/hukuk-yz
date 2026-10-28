import type { createApiClient } from "@hukuk/web-core/api/client";
import { unwrap } from "@hukuk/web-core/api/unwrap";

import type { FeedbackIn } from "./chat-types";

type Api = ReturnType<typeof createApiClient>;

export function createConversation(api: Api) {
    // The API takes an unsafe request only as JSON; this one has no body to make the client add the header.
    return unwrap(
        api.POST("/chat/conversations", { headers: { "Content-Type": "application/json" } }),
    );
}

export async function listConversations(api: Api) {
    return (await unwrap(api.GET("/chat/conversations"))).items;
}

export function postFeedback(api: Api, turnId: string, body: FeedbackIn) {
    return unwrap(
        api.POST("/chat/turns/{turn_id}/feedback", {
            params: { path: { turn_id: turnId } },
            body,
        }),
    );
}
