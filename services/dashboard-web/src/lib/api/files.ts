import "server-only";

import { cache } from "react";

import { createServerApi } from "./server";
import { PENDING_COUNT_LIMIT, type PendingFiles } from "@/lib/files";

/**
 * How many files wait for approval, for the menu and the list tab: counted from one page of the
 * list (the API has no total), so `more` says there are at least that many. Null when the list
 * could not be fetched: no count is shown rather than failing the page. One request per render.
 */
export const getPendingFiles = cache(async (): Promise<PendingFiles | null> => {
    const api = await createServerApi();
    const answer = await api
        .GET("/files", {
            params: { query: { review_status: "pending", limit: PENDING_COUNT_LIMIT } },
        })
        .catch(() => null);
    return answer?.data
        ? { count: answer.data.items.length, more: answer.data.next_cursor !== null }
        : null;
});

/** The names of the files a pending file matched, by id; a file that cannot be read is left out. */
export async function getFileNames(ids: string[]): Promise<Record<string, string>> {
    const api = await createServerApi();
    const found = await Promise.all(
        ids.map(async (id) => {
            const answer = await api
                .GET("/files/{file_id}", { params: { path: { file_id: id } } })
                .catch(() => null);
            const name = answer?.data?.original_name ?? answer?.data?.title;
            return name ? ([id, name] as const) : null;
        }),
    );
    return Object.fromEntries(found.filter((entry) => entry !== null));
}
