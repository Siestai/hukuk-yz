import "server-only";

import { cache } from "react";

import { settle } from "./settle";
import { createServerApi } from "./server";

/** The signed-in user; one request per render pass however many components ask. */
export const getMe = cache(async () => {
    const api = await createServerApi();
    const me = await settle(api.GET("/auth/me"), "GET /auth/me");
    if (me.error) throw new Error(`GET /auth/me failed with ${me.error.code ?? "an error"}`);
    return me.data;
});
