import type { NextRequest } from "next/server";

import { appApiUrl } from "@/lib/env";
import { apiFrameHeaders } from "@/lib/security-headers";
import { upstreamHeaders } from "@/lib/upstream";

// Browser -> this server -> `app`: `app` is never exposed. Only the prefixes the UI uses pass; under
// them every method is allowed, and `app` decides (authorization lives there, not here).
// `files` itself is the list and the upload (`POST /files`), so it passes without a trailing path.
const ALLOWED_PREFIXES = ["auth/", "review/", "files/"];
const ALLOWED_PATHS = ["files"];
const TIMEOUT_MS = 30_000;
// Requests the UI sends are small JSON; anything larger is refused before it reaches `app`.
const MAX_BODY_BYTES = 1024 * 1024;
// Only a file upload is large: `app` allows 50 MB per file (`FILE_MAX_BYTES`, enforced there with
// its own `file_too_large`); this cap leaves room for the multipart envelope. The wait for the
// answer includes sending the body, so an upload gets a longer timeout.
const isFilesPath = (path: string) => path === "files" || path.startsWith("files/");
const MAX_FILE_BODY_BYTES = 64 * 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 5 * 60_000;
// The only request headers forwarded besides the ones `upstreamHeaders` builds.
const REQUEST_HEADERS = ["content-type", "accept", "x-requested-with"];
// The only response headers passed back (this also drops hop-by-hop ones); set-cookie is handled apart.
const RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control", "retry-after"];

/** Passes the body through and errors the stream (and flags it) once it exceeds the cap. */
function capBody(body: ReadableStream<Uint8Array>, limit: number, onExceeded: () => void) {
    let seen = 0;
    return body.pipeThrough(
        new TransformStream<Uint8Array, Uint8Array>({
            transform(chunk, controller) {
                seen += chunk.byteLength;
                if (seen > limit) {
                    onExceeded();
                    controller.error(new Error("request body too large"));
                    return;
                }
                controller.enqueue(chunk);
            },
        }),
    );
}

// Set here, never taken from upstream, on every response of the route, its own errors included.
function withFrameHeaders(headers: Headers, pathname: string): Headers {
    for (const [name, value] of Object.entries(apiFrameHeaders(pathname))) {
        headers.set(name, value);
    }
    return headers;
}

function errorResponse(status: number, code: string, pathname: string): Response {
    return Response.json(
        { error: { code, params: {} } },
        { status, headers: withFrameHeaders(new Headers(), pathname) },
    );
}

async function forward(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
    const segments = (await params).path;
    const { pathname } = request.nextUrl;
    const path = segments.join("/");
    if (
        !(
            ALLOWED_PATHS.includes(path) ||
            ALLOWED_PREFIXES.some((prefix) => path.startsWith(prefix))
        ) ||
        segments.some((s) => s === "." || s === ".." || s.includes("/") || s.includes("\\"))
    ) {
        return errorResponse(404, "not_found", pathname);
    }

    const headers = upstreamHeaders(request.headers, request.nextUrl.protocol);
    for (const name of REQUEST_HEADERS) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
    }
    const url = `${appApiUrl()}/${segments.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
    const hasBody = request.method !== "GET" && request.method !== "HEAD";
    const isUpload = hasBody && isFilesPath(path);
    const limit = isUpload ? MAX_FILE_BODY_BYTES : MAX_BODY_BYTES;
    if (hasBody && Number(request.headers.get("content-length")) > limit) {
        return errorResponse(413, "payload_too_large", pathname);
    }
    let tooLarge = false;
    const body =
        hasBody && request.body ? capBody(request.body, limit, () => (tooLarge = true)) : undefined;

    // The timeout covers the wait for the response head; a long body (a PDF) streams after it.
    // A client that goes away aborts the upstream request at any point, body included.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), isUpload ? UPLOAD_TIMEOUT_MS : TIMEOUT_MS);
    let upstream: Response;
    try {
        upstream = await fetch(url, {
            method: request.method,
            headers,
            body,
            ...(body ? { duplex: "half" } : {}),
            redirect: "manual",
            signal: AbortSignal.any([request.signal, controller.signal]),
        });
    } catch {
        if (tooLarge) return errorResponse(413, "payload_too_large", pathname);
        return errorResponse(
            controller.signal.aborted ? 504 : 502,
            "upstream_unavailable",
            pathname,
        );
    } finally {
        clearTimeout(timer);
    }

    const out = new Headers();
    for (const name of RESPONSE_HEADERS) {
        const value = upstream.headers.get(name);
        if (value) out.set(name, value);
    }
    // The allowlist above drops any CSP or frame header of `app`.
    withFrameHeaders(out, pathname);
    for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
    return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
