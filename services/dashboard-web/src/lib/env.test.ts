import { afterEach, describe, expect, it, vi } from "vitest";

import { appApiUrl } from "./env";

afterEach(() => vi.unstubAllEnvs());

describe("appApiUrl", () => {
    it("returns the URL without a trailing slash", () => {
        vi.stubEnv("APP_API_URL", "http://localhost:8000/");
        expect(appApiUrl()).toBe("http://localhost:8000");
    });

    it("fails clearly when unset or invalid", () => {
        vi.stubEnv("APP_API_URL", "");
        expect(() => appApiUrl()).toThrow(/APP_API_URL is not set/);
        vi.stubEnv("APP_API_URL", "not a url");
        expect(() => appApiUrl()).toThrow(/not a valid URL/);
    });
});
