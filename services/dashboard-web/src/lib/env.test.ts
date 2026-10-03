import { afterEach, describe, expect, it, vi } from "vitest";

import { appApiUrl, trustedProxyHops } from "./env";

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

describe("trustedProxyHops", () => {
    it("defaults to 1", () => {
        vi.stubEnv("TRUSTED_PROXY_HOPS", "");
        expect(trustedProxyHops()).toBe(1);
    });

    it("reads a positive integer", () => {
        vi.stubEnv("TRUSTED_PROXY_HOPS", "2");
        expect(trustedProxyHops()).toBe(2);
    });

    it.each(["0", "-1", "1.5", "two", "1e1"])("fails clearly on %j", (value) => {
        vi.stubEnv("TRUSTED_PROXY_HOPS", value);
        expect(() => trustedProxyHops()).toThrow(/TRUSTED_PROXY_HOPS/);
    });
});
