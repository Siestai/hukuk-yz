import "server-only";

import { getMe } from "@hukuk/web-core/api/me";
import { createServerApi } from "@hukuk/web-core/api/server";
import { settle } from "@hukuk/web-core/api/settle";

/** The conversations of the signed-in user, and (when `conversationId` is given) that conversation. */
export async function loadChat(conversationId?: string) {
    const api = await createServerApi();
    await getMe();
    const [list, detail] = await Promise.all([
        settle(api.GET("/chat/conversations"), "GET /chat/conversations"),
        conversationId
            ? settle(
                  api.GET("/chat/conversations/{conversation_id}", {
                      params: { path: { conversation_id: conversationId } },
                  }),
                  "GET /chat/conversations/{id}",
              )
            : null,
    ]);
    if (list.error) throw new Error(`GET /chat/conversations failed with ${list.error.code}`);
    return {
        conversations: list.data.items,
        detail: detail?.data ?? null,
        missing: Boolean(detail?.error),
    };
}
