import { describe, expect, it } from "vitest";

import { safeNextPath } from "./next-path";

describe("safeNextPath", () => {
    it.each(["/", "/inceleme", "/inceleme?band=high&page=2", "/a/b#c"])("keeps %s", (path) => {
        expect(safeNextPath(path)).toBe(path);
    });

    it.each([
        "//evil.example",
        "http://evil.example",
        "https://evil.example/x",
        "/\\evil.example",
        "/\\/evil.example",
        "javascript:alert(1)",
        "evil",
        "",
        "/a\nb",
        "/giris",
        "/giris?next=/",
        "/giris/",
        "/giris?x",
        "/girisx",
        "/oturum-sonu",
        "/oturum-sonu?x=1",
        "/api/auth/logout",
    ])("rejects %j", (path) => {
        expect(safeNextPath(path)).toBe("/");
    });

    it("falls back for a missing value", () => {
        expect(safeNextPath(undefined)).toBe("/");
        expect(safeNextPath(null)).toBe("/");
    });
});
