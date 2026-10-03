// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DELETE, GET, POST } from "./route";

const fetchMock = vi.fn();

beforeEach(() => {
    vi.stubEnv("APP_API_URL", "http://app:8000/");
    vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    fetchMock.mockReset();
});

const call = (
    handler: typeof GET,
    path: string,
    init: ConstructorParameters<typeof NextRequest>[1] = {},
) =>
    handler(new NextRequest(`http://dash.test/api/${path}`, init), {
        params: Promise.resolve({ path: path.split("?")[0]!.split("/") }),
    });
const upstreamCall = () => {
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Headers }];
    return { url, init };
};

describe("api proxy", () => {
    it("forwards method, query, body, content type, cookie and the client address", async () => {
        fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
        const response = await call(POST, "auth/login?x=1", {
            method: "POST",
            body: JSON.stringify({ email: "a@b.c" }),
            headers: {
                "content-type": "application/json",
                accept: "application/json",
                cookie: "hukuk_session=abc",
                "x-forwarded-for": "6.6.6.6, 203.0.113.7",
                "x-forwarded-proto": "https",
                authorization: "Bearer nope",
            },
        });
        const { url, init } = upstreamCall();
        expect(response.status).toBe(204);
        expect(url).toBe("http://app:8000/auth/login?x=1");
        expect(init.method).toBe("POST");
        expect(await new Response(init.body as ReadableStream).text()).toBe('{"email":"a@b.c"}');
        expect(init.headers.get("content-type")).toBe("application/json");
        expect(init.headers.get("accept")).toBe("application/json");
        expect(init.headers.get("cookie")).toBe("hukuk_session=abc");
        expect(init.headers.get("x-forwarded-for")).toBe("203.0.113.7");
        expect(init.headers.get("x-forwarded-proto")).toBe("https");
        expect(init.headers.get("authorization")).toBeNull();
    });

    it("sends no body for GET and forwards DELETE", async () => {
        fetchMock.mockResolvedValue(new Response("{}"));
        await call(GET, "review/decisions/summary");
        expect(upstreamCall().init.body).toBeUndefined();
        fetchMock.mockClear();
        await call(DELETE, "review/decisions/1", { method: "DELETE" });
        expect(upstreamCall().init.method).toBe("DELETE");
    });

    it.each(["internal/health", "authx/login", "auth", "", "docs"])(
        "answers 404 not_found for %j without calling the API",
        async (path) => {
            const response = await call(GET, path);
            expect(response.status).toBe(404);
            expect(await response.json()).toEqual({ error: { code: "not_found", params: {} } });
            expect(fetchMock).not.toHaveBeenCalled();
        },
    );

    it.each([
        ["a dot-dot segment", ["review", "..", "x"]],
        ["an encoded slash inside one segment", ["review%2F..%2Fx"]],
        ["a decoded slash inside one segment", ["review/../x"]],
    ])("refuses path traversal: %s", async (_name, path) => {
        const response = await GET(new NextRequest("http://dash.test/api/review/x"), {
            params: Promise.resolve({ path }),
        });
        expect(response.status).toBe(404);
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it("aborts the upstream request when the client goes away", async () => {
        fetchMock.mockResolvedValue(new Response("{}"));
        const client = new AbortController();
        await call(GET, "review/decisions/1/file", { signal: client.signal });
        const { signal } = upstreamCall().init;
        expect(signal?.aborted).toBe(false);
        client.abort();
        expect(signal?.aborted).toBe(true);
    });

    it("refuses a body that declares more than 1 MB", async () => {
        const response = await call(POST, "review/decisions/1", {
            method: "POST",
            body: "{}",
            headers: { "content-length": String(1024 * 1024 + 1) },
        });
        expect(response.status).toBe(413);
        expect(await response.json()).toEqual({
            error: { code: "payload_too_large", params: {} },
        });
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it("stops a streamed body that grows past 1 MB", async () => {
        fetchMock.mockImplementation(async (_url: string, init: RequestInit) => {
            await new Response(init.body).text();
            return new Response(null, { status: 204 });
        });
        const chunk = new Uint8Array(600 * 1024);
        const body = new ReadableStream<Uint8Array>({
            start(controller) {
                controller.enqueue(chunk);
                controller.enqueue(chunk);
                controller.close();
            },
        });
        const response = await call(POST, "review/decisions/1", {
            method: "POST",
            body,
            duplex: "half",
        } as ConstructorParameters<typeof NextRequest>[1]);
        expect(response.status).toBe(413);
        expect((await response.json()).error.code).toBe("payload_too_large");
    });

    it("lets a body under the cap through", async () => {
        fetchMock.mockImplementation(async (_url: string, init: RequestInit) => {
            await new Response(init.body).text();
            return new Response(null, { status: 204 });
        });
        const response = await call(POST, "review/decisions/1", {
            method: "POST",
            body: "x".repeat(1024),
        });
        expect(response.status).toBe(204);
    });

    it("passes status, set-cookie, retry-after and content headers, drops the rest", async () => {
        const upstream = new Response(JSON.stringify({ error: { code: "too_many_attempts" } }), {
            status: 429,
            headers: {
                "content-type": "application/json",
                "retry-after": "840",
                "cache-control": "no-store",
                "content-disposition": 'inline; filename="k.pdf"',
                connection: "keep-alive",
                "x-powered-by": "app",
            },
        });
        upstream.headers.append("set-cookie", "hukuk_session=a; Path=/; HttpOnly");
        upstream.headers.append("set-cookie", "other=b; Path=/");
        fetchMock.mockResolvedValue(upstream);
        const response = await call(POST, "auth/login", { method: "POST", body: "{}" });
        expect(response.status).toBe(429);
        expect(response.headers.get("retry-after")).toBe("840");
        expect(response.headers.get("cache-control")).toBe("no-store");
        expect(response.headers.get("content-disposition")).toContain("k.pdf");
        expect(response.headers.getSetCookie()).toHaveLength(2);
        expect(response.headers.get("connection")).toBeNull();
        expect(response.headers.get("x-powered-by")).toBeNull();
    });

    it("streams binary bodies through", async () => {
        const bytes = new Uint8Array([37, 80, 68, 70, 0, 255]);
        fetchMock.mockResolvedValue(
            new Response(bytes, { headers: { "content-type": "application/pdf" } }),
        );
        const response = await call(GET, "review/decisions/1/file");
        expect(response.headers.get("content-type")).toBe("application/pdf");
        expect(new Uint8Array(await response.arrayBuffer())).toEqual(bytes);
    });

    it("lets only our own pages frame the original PDF and ignores the upstream CSP", async () => {
        const id = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
        fetchMock.mockImplementation(
            async () =>
                new Response("%PDF", {
                    headers: {
                        "content-type": "application/pdf",
                        "content-disposition": 'inline; filename="k.pdf"',
                        "content-security-policy": "frame-ancestors *",
                        "x-frame-options": "ALLOWALL",
                    },
                }),
        );
        const pdf = await call(GET, `review/decisions/${id}/file`);
        expect(pdf.headers.get("content-type")).toBe("application/pdf");
        expect(pdf.headers.get("content-disposition")).toContain("inline");
        expect(pdf.headers.get("content-security-policy")).toBe("frame-ancestors 'self'");
        expect(pdf.headers.get("x-frame-options")).toBe("SAMEORIGIN");
        const other = await call(GET, `review/decisions/${id}`);
        expect(other.headers.get("content-security-policy")).toBe("frame-ancestors 'none'");
        expect(other.headers.get("x-frame-options")).toBe("DENY");
    });

    it("maps a refused connection to 502 upstream_unavailable", async () => {
        fetchMock.mockRejectedValue(new TypeError("fetch failed"));
        const response = await call(GET, "auth/me");
        expect(response.status).toBe(502);
        expect(await response.json()).toEqual({
            error: { code: "upstream_unavailable", params: {} },
        });
    });

    it("maps a timeout to 504 upstream_unavailable", async () => {
        vi.useFakeTimers();
        try {
            fetchMock.mockImplementation(
                (_url: string, init: RequestInit) =>
                    new Promise((_resolve, reject) => {
                        init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
                    }),
            );
            const pending = call(GET, "auth/me");
            await vi.advanceTimersByTimeAsync(30_000);
            const response = await pending;
            expect(response.status).toBe(504);
            expect(await response.json()).toEqual({
                error: { code: "upstream_unavailable", params: {} },
            });
        } finally {
            vi.useRealTimers();
        }
    });
});
