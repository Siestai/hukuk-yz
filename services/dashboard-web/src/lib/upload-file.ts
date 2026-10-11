import { apiError } from "@/lib/api/errors";
import type { FileOut } from "@/lib/files";

export type UploadFields = {
    doc_type?: string;
    doc_date?: string;
    official_ref?: string;
    origin_url?: string;
    note?: string;
};

export type UploadOutcome =
    | { ok: true; file: FileOut }
    | { ok: false; code: string | undefined; params: Record<string, unknown> };

const lost = (): UploadOutcome => ({ ok: false, code: "upstream_unavailable", params: {} });

/**
 * Sends one file as `multipart/form-data` to `url` (`POST /files` or `POST /files/{id}/versions`
 * through the BFF proxy). `fetch` reports no upload progress, hence XMLHttpRequest; the answer is
 * the API's `FileOut` or its `{error: {code, params}}` body. Never rejects: a network failure is
 * an `upstream_unavailable` outcome.
 */
export function uploadFile(
    url: string,
    file: File,
    fields: UploadFields,
    onProgress: (fraction: number) => void,
): Promise<UploadOutcome> {
    const form = new FormData();
    for (const [name, value] of Object.entries(fields)) {
        if (value) form.set(name, value);
    }
    form.set("file", file);

    return new Promise((resolve) => {
        const request = new XMLHttpRequest();
        request.open("POST", url);
        request.responseType = "json";
        // The API takes a multipart POST by session cookie only with this header (CSRF, `app.auth`).
        request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        request.upload.onprogress = (event) => {
            if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
        };
        request.onerror = () => resolve(lost());
        request.ontimeout = () => resolve(lost());
        request.onload = () => {
            if (request.status === 201 && request.response) {
                resolve({ ok: true, file: request.response as FileOut });
                return;
            }
            const { code, params } = apiError(request.response);
            // The proxy refuses an oversized body with its own code before the API sees it.
            const sized = request.status === 413 ? "file_too_large" : code;
            resolve({ ok: false, code: sized, params });
        };
        request.send(form);
    });
}
