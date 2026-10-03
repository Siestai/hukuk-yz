import { describe, expect, it } from "vitest";

import config from "../../next.config";
import { apiFrameHeaders, contentSecurityPolicy, staticSecurityHeaders } from "./security-headers";

const directives = (csp: string) =>
    Object.fromEntries(csp.split("; ").map((d) => [d.split(" ")[0], d]));

describe("contentSecurityPolicy", () => {
    const csp = directives(contentSecurityPolicy("abc", false));

    it("allows scripts only with the nonce and never eval in production", () => {
        expect(csp["script-src"]).toBe("script-src 'self' 'nonce-abc' 'strict-dynamic'");
    });

    it.each([
        ["default-src", "default-src 'self'"],
        ["style-src", "style-src 'self' 'unsafe-inline'"],
        ["img-src", "img-src 'self' data:"],
        ["font-src", "font-src 'self'"],
        ["connect-src", "connect-src 'self'"],
        ["frame-src", "frame-src 'self'"],
        ["object-src", "object-src 'none'"],
        ["frame-ancestors", "frame-ancestors 'none'"],
        ["base-uri", "base-uri 'self'"],
        ["form-action", "form-action 'self'"],
    ])("sets %s", (name, value) => {
        expect(csp[name]).toBe(value);
    });

    it("relaxes scripts and connections for HMR in development only", () => {
        const dev = directives(contentSecurityPolicy("abc", true));
        expect(dev["script-src"]).toContain("'unsafe-eval'");
        expect(dev["connect-src"]).toContain("ws:");
    });
});

describe("staticSecurityHeaders", () => {
    const asMap = (isDev: boolean) =>
        Object.fromEntries(staticSecurityHeaders(isDev).map((h) => [h.key, h.value]));

    it("sets the fixed headers", () => {
        expect(asMap(false)).toMatchObject({
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
            "X-Robots-Tag": "noindex, nofollow",
        });
    });

    it("sends HSTS outside development only", () => {
        expect(asMap(false)).toHaveProperty("Strict-Transport-Security");
        expect(asMap(true)).not.toHaveProperty("Strict-Transport-Security");
    });

    it("is applied to every path by next.config", async () => {
        const rules = await config.headers?.();
        expect(rules?.[0]?.source).toBe("/:path*");
        expect(rules?.[0]?.headers.map((h) => h.key)).toContain("X-Content-Type-Options");
    });
});

describe("apiFrameHeaders", () => {
    const id = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";

    it("lets the same origin frame the PDF of a decision", () => {
        expect(apiFrameHeaders(`/api/review/decisions/${id}/file`)).toEqual({
            "Content-Security-Policy": "frame-ancestors 'self'",
            "X-Frame-Options": "SAMEORIGIN",
        });
    });

    it.each([
        `/api/review/decisions/${id}`,
        `/api/review/decisions/${id}/file/extra`,
        `/api/review/decisions/${id}/files`,
        "/api/review/decisions/not-a-uuid/file",
        "/api/auth/me",
        "/",
    ])("forbids framing %s", (path) => {
        expect(apiFrameHeaders(path)).toEqual({
            "Content-Security-Policy": "frame-ancestors 'none'",
            "X-Frame-Options": "DENY",
        });
    });
});
