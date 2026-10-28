import { frameHeaders } from "@hukuk/web-core/lib/security-headers";

import { UUID } from "./uuid";

const PDF_FILE_PATH = new RegExp(
    `^/api/(?:review/decisions/${UUID.source}/file|files/${UUID.source}/content)$`,
    "i",
);

/**
 * Framing headers of an `/api` response. Two exact
 * paths are shown in an iframe of our own pages: the original PDF of a decision and the content
 * of a stored file. Only those may be framed, and only by the same origin; the rest never.
 */
export function apiFrameHeaders(pathname: string): Record<string, string> {
    return frameHeaders(PDF_FILE_PATH.test(pathname));
}
