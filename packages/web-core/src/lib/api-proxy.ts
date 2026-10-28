import type { NextRequest } from "next/server";

import { appApiUrl } from "./env";
import { upstreamHeaders } from "./upstream";

export type ApiProxyOptions = {
    /** Browser -> this server -> `app`: only these prefixes (and exact paths) pass, every method; `app` decides. */
    allowedPrefixes: string[];
    allowedPaths?: string[];
    /** Set here, never taken from upstream, on every response of the route, its own errors included. */
    frameHeaders: (pathname: string) => Record<string, string>;
    /** Body cap and wait for the response head of a request; the default fits small JSON. */
    limits?: (method: string, path: string) => { maxBodyBytes: number; timeoutMs: number };
};

// Requests the UI sends are small JSON; anything larger is refused before it reaches `app`.
export const DEFAULT_LIMITS = { maxBodyBytes: 1024 * 1024, timeoutMs: 30_000 };
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

/** The route handler of `/api/[...path]`: forwards to `app` with the session cookie, streams the answer back. */
export function createApiProxy({
    allowedPrefixes,
    allowedPaths = [],
    frameHeaders,
    limits = () => DEFAULT_LIMITS,
}: ApiProxyOptions) {
    function withFrameHeaders(headers: Headers, pathname: string): Headers {
        for (const [name, value] of Object.entries(frameHeaders(pathname))) {
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

    return async function forward(
        request: NextRequest,
        { params }: { params: Promise<{ path: string[] }> },
    ): Promise<Response> {
        const segments = (await params).path;
        const { pathname } = request.nextUrl;
        const path = segments.join("/");
        if (
            !(
                allowedPaths.includes(path) ||
                allowedPrefixes.some((prefix) => path.startsWith(prefix))
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
        const { maxBodyBytes, timeoutMs } = limits(request.method, path);
        if (hasBody && Number(request.headers.get("content-length")) > maxBodyBytes) {
            return errorResponse(413, "payload_too_large", pathname);
        }
        let tooLarge = false;
        const body =
            hasBody && request.body
                ? capBody(request.body, maxBodyBytes, () => (tooLarge = true))
                : undefined;

        // The timeout covers the wait for the response head; a long body (a PDF, an event stream)
        // streams after it. A client that goes away aborts the upstream request at any point.
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
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
    };
}
