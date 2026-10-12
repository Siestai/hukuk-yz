import type { createApiClient } from "./client";
import { apiError } from "./errors";
import type { components } from "./schema";
import { ApiFailure, unwrap } from "./review-client";

type Api = ReturnType<typeof createApiClient>;

/**
 * The API takes an unsafe request by session cookie only with `Content-Type: application/json`
 * (CSRF, `app.auth`), and a request without a body carries none of its own.
 */
const JSON_TYPE = { headers: { "Content-Type": "application/json" } } as const;

/** The admin actions on a file; each answers the updated record or throws an `ApiFailure`. */
export function postFileAction(
    api: Api,
    fileId: string,
    action: "archive" | "unarchive" | "rescan" | "unapprove",
) {
    const params = { params: { path: { file_id: fileId } }, ...JSON_TYPE };
    switch (action) {
        case "archive":
            return unwrap(api.POST("/files/{file_id}/archive", params));
        case "unarchive":
            return unwrap(api.POST("/files/{file_id}/unarchive", params));
        case "rescan":
            return unwrap(api.POST("/files/{file_id}/rescan", params));
        case "unapprove":
            return unwrap(api.POST("/files/{file_id}/unapprove", params));
    }
}

export type FileApproval = components["schemas"]["FileApproval"];

/** Approves a pending file with its final fields (`POST /files/{id}/approve`). */
export function approveFile(api: Api, fileId: string, body: FileApproval) {
    return unwrap(
        api.POST("/files/{file_id}/approve", { params: { path: { file_id: fileId } }, body }),
    );
}

/** Deletes a pending file (`DELETE /files/{id}`, 204 without a body). */
export async function deleteFile(api: Api, fileId: string): Promise<void> {
    const answer = await api
        .DELETE("/files/{file_id}", { params: { path: { file_id: fileId } }, ...JSON_TYPE })
        .catch(() => {
            throw new ApiFailure("upstream_unavailable");
        });
    if (!answer.response.ok) {
        const { code, params } = apiError(answer.error);
        throw new ApiFailure(code, params);
    }
}

/** The text the scan extracted (`GET /files/{id}/text`). */
export function getFileText(api: Api, fileId: string) {
    return unwrap(
        api.GET("/files/{file_id}/text", {
            params: { path: { file_id: fileId } },
            parseAs: "text",
        }),
    );
}
