import "server-only";

import { cache } from "react";

import { createServerApi } from "./server";

/** Shared by the layout badge and the queue page, so one request fetches it once. */
export const getReviewSummary = cache(async () => {
    const api = await createServerApi();
    return api.GET("/review/decisions/summary");
});
