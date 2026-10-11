import type { createApiClient } from "./client";
import { unwrap } from "./review-client";

type Api = ReturnType<typeof createApiClient>;

/** The admin actions on a file; each answers the updated record or throws an `ApiFailure`. */
export function postFileAction(
    api: Api,
    fileId: string,
    action: "archive" | "unarchive" | "rescan",
) {
    const params = { params: { path: { file_id: fileId } } };
    switch (action) {
        case "archive":
            return unwrap(api.POST("/files/{file_id}/archive", params));
        case "unarchive":
            return unwrap(api.POST("/files/{file_id}/unarchive", params));
        case "rescan":
            return unwrap(api.POST("/files/{file_id}/rescan", params));
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
