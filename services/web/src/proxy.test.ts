// @vitest-environment node
import { describe, expect, it } from "vitest";

import { config } from "./proxy";

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
