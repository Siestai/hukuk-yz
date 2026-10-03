// @vitest-environment node
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { config, proxy } from "./proxy";

const get = (path: string, cookie?: string) =>
    proxy(
        new NextRequest(`http://localhost:3000${path}`, {
            headers: cookie ? { cookie } : {},
        }),
    );
const session = "hukuk_session=abc";
const target = (response: Response) => {
    const location = new URL(response.headers.get("location") ?? "", "http://x.invalid");
    return location.pathname + location.search;
};

describe("proxy", () => {
    it("sends a request without a session to /giris", () => {
        const response = get("/");
        expect(response.status).toBe(307);
        expect(target(response)).toBe("/giris");
    });

    it("keeps the intended path in ?next=", () => {
        const response = get("/inceleme?band=high");
        expect(target(response)).toBe(`/giris?next=${encodeURIComponent("/inceleme?band=high")}`);
    });

    it("lets the login page and the stale-session route through without a session", () => {
        for (const path of ["/giris", "/oturum-sonu"]) {
            const response = get(path);
            expect(response.status).toBe(200);
            expect(response.headers.get("location")).toBeNull();
        }
    });

    it("sends a signed-in user from /giris to /", () => {
        const response = get("/giris", session);
        expect(response.status).toBe(307);
        expect(target(response)).toBe("/");
    });

    it("lets a signed-in user through", () => {
        expect(get("/", session).status).toBe(200);
    });

    it("sets a CSP whose script nonce is passed to the page and differs per request", () => {
        const [a, b] = [get("/giris"), get("/giris")];
        const csp = a.headers.get("content-security-policy") ?? "";
        const nonce = /'nonce-([^']+)'/.exec(csp)?.[1];
        expect(nonce).toBeTruthy();
        expect(a.headers.get("x-middleware-request-x-nonce")).toBe(nonce);
        expect(b.headers.get("content-security-policy")).not.toBe(csp);
    });
});

describe("proxy matcher", () => {
    // Next compiles `source` with path-to-regexp and anchors it, so a negative lookahead excludes
    // exactly the listed paths. This mirrors that: the pattern in an anchored RegExp.
    const source = (config.matcher[0] as { source: string }).source;
    const matches = (path: string) => new RegExp(`^${source}$`).test(path);

    it("skips /healthz but not /healthz/x or pages", () => {
        expect(matches("/healthz")).toBe(false);
        expect(matches("/healthz/x")).toBe(true);
        expect(matches("/giris")).toBe(true);
        expect(matches("/")).toBe(true);
    });

    it("skips the API proxy and static assets", () => {
        expect(matches("/api/auth/me")).toBe(false);
        expect(matches("/_next/static/a.css")).toBe(false);
        expect(matches("/favicon.ico")).toBe(false);
    });
});
