import { apiError } from "@hukuk/web-core/api/errors";
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
// A 2xx that is not the expected 201 with a file, or a body that is not JSON.
const unexpected = (): UploadOutcome => ({ ok: false, code: "invalid_response", params: {} });
// As long as the proxy waits for an upload (`UPLOAD_TIMEOUT_MS` in the BFF route).
const TIMEOUT_MS = 5 * 60_000;

/**
 * Sends one file as `multipart/form-data` to `url` (`POST /files` or `POST /files/{id}/versions`
 * through the BFF proxy). `fetch` reports no upload progress, hence XMLHttpRequest; the answer is
 * the API's `FileOut` or its `{error: {code, params}}` body. Never rejects: a network failure is
 * an `upstream_unavailable` outcome, and so are an abort and a timeout; an answer that is not
 * the API's is `invalid_response`.
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
        request.timeout = TIMEOUT_MS;
        // The API takes a multipart POST by session cookie only with this header (CSRF, `app.auth`).
        request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        request.upload.onprogress = (event) => {
            if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
        };
        request.onerror = () => resolve(lost());
        request.onabort = () => resolve(lost());
        request.ontimeout = () => resolve(lost());
        request.onload = () => {
            if (request.status === 201 && request.response) {
                resolve({ ok: true, file: request.response as FileOut });
                return;
            }
            if (request.status >= 200 && request.status < 300) {
                resolve(unexpected());
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
