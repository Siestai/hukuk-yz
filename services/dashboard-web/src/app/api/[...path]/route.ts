import type { NextRequest } from "next/server";

import { appApiUrl } from "@/lib/env";
import { upstreamHeaders } from "@/lib/upstream";

// Browser -> this server -> `app`: `app` is never exposed. Only the prefixes the UI uses pass.
const ALLOWED_PREFIXES = ["auth/", "review/"];
const TIMEOUT_MS = 30_000;
// The only request headers forwarded besides the ones `upstreamHeaders` builds.
const REQUEST_HEADERS = ["content-type", "accept"];
// The only response headers passed back (this also drops hop-by-hop ones); set-cookie is handled apart.
const RESPONSE_HEADERS = ["content-type", "content-disposition", "cache-control", "retry-after"];

function errorResponse(status: number, code: string): Response {
    return Response.json({ error: { code, params: {} } }, { status });
}

async function forward(
    request: NextRequest,
    { params }: { params: Promise<{ path: string[] }> },
): Promise<Response> {
    const segments = (await params).path;
    const path = segments.join("/");
    if (
        !ALLOWED_PREFIXES.some((prefix) => path.startsWith(prefix)) ||
        segments.some((s) => s === "." || s === ".." || s.includes("/") || s.includes("\\"))
    ) {
        return errorResponse(404, "not_found");
    }

    const headers = upstreamHeaders(request.headers, request.nextUrl.protocol);
    for (const name of REQUEST_HEADERS) {
        const value = request.headers.get(name);
        if (value) headers.set(name, value);
    }
    const url = `${appApiUrl()}/${segments.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
    const hasBody = request.method !== "GET" && request.method !== "HEAD";

    // The timeout covers the wait for the response head; a long body (a PDF) streams after it.
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    let upstream: Response;
    try {
        upstream = await fetch(url, {
            method: request.method,
            headers,
            body: hasBody ? request.body : undefined,
            ...(hasBody ? { duplex: "half" } : {}),
            redirect: "manual",
            signal: controller.signal,
        });
    } catch {
        return errorResponse(controller.signal.aborted ? 504 : 502, "upstream_unavailable");
    } finally {
        clearTimeout(timer);
    }

    const out = new Headers();
    for (const name of RESPONSE_HEADERS) {
        const value = upstream.headers.get(name);
        if (value) out.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
    return new Response(upstream.body, { status: upstream.status, headers: out });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
