import { describe, expect, it } from "vitest";

import config from "../../next.config";
import { apiFrameHeaders } from "./security-headers";

describe("next.config", () => {
    it("applies the static security headers to every path", async () => {
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

    it("lets the same origin frame the content of a stored file", () => {
        expect(apiFrameHeaders(`/api/files/${id}/content`)).toMatchObject({
            "X-Frame-Options": "SAMEORIGIN",
        });
        expect(apiFrameHeaders(`/api/files/${id}/text`)).toMatchObject({
            "X-Frame-Options": "DENY",
        });
    });

    it("matches the UUID in upper case", () => {
        expect(apiFrameHeaders(`/api/review/decisions/${id.toUpperCase()}/file`)).toMatchObject({
            "X-Frame-Options": "SAMEORIGIN",
        });
    });

    it.each([
        `/api/review/decisions/%33f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10/file`,
        `/api/review/decisions/${encodeURIComponent(id)}%2Ffile`,
        `/api/review/decisions/${id}/file/x`,
        `/api/files/${id}/content/x`,
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
