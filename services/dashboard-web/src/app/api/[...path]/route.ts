import { createApiProxy, DEFAULT_LIMITS } from "@hukuk/web-core/lib/api-proxy";

import { apiFrameHeaders } from "@/lib/security-headers";
import { UUID } from "@/lib/uuid";

// `files` itself is the list and the upload (`POST /files`), so it passes without a trailing path.
// Only a file upload (`POST files`, `POST files/<uuid>/versions`) is large: `app` allows 50 MB per
// file (`FILE_MAX_BYTES`, enforced there with its own `file_too_large`); this cap leaves room for
// the multipart envelope. The wait for the answer includes sending the body, so an upload gets a
// longer timeout. Every other method and path keeps the small limits.
const UPLOAD_PATH = new RegExp(`^files(?:/${UUID.source}/versions)?$`, "i");
const MAX_FILE_BODY_BYTES = 64 * 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 5 * 60_000;

const forward = createApiProxy({
    allowedPrefixes: ["auth/", "review/", "files/"],
    allowedPaths: ["files"],
    frameHeaders: apiFrameHeaders,
    limits: (method, path) =>
        method === "POST" && UPLOAD_PATH.test(path)
            ? { maxBodyBytes: MAX_FILE_BODY_BYTES, timeoutMs: UPLOAD_TIMEOUT_MS }
            : DEFAULT_LIMITS,
});

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
