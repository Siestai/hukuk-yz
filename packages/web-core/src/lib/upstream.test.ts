import { afterEach, describe, expect, it, vi } from "vitest";

import { upstreamHeaders } from "./upstream";

afterEach(() => vi.unstubAllEnvs());

const forwarded = (xff?: string) =>
    upstreamHeaders(new Headers(xff === undefined ? {} : { "x-forwarded-for": xff }), "http:").get(
        "x-forwarded-for",
    );

describe("upstreamHeaders client address", () => {
    it("takes the last hop by default", () => {
        expect(forwarded("6.6.6.6, 203.0.113.7")).toBe("203.0.113.7");
    });

    it("counts TRUSTED_PROXY_HOPS from the right", () => {
        vi.stubEnv("TRUSTED_PROXY_HOPS", "2");
        expect(forwarded("6.6.6.6, 203.0.113.7, 10.0.0.1")).toBe("203.0.113.7");
        expect(forwarded("6.6.6.6, 203.0.113.7")).toBe("6.6.6.6");
    });

    it("sends none without the header or with too few hops", () => {
        expect(forwarded()).toBeNull();
        vi.stubEnv("TRUSTED_PROXY_HOPS", "2");
        expect(forwarded("203.0.113.7")).toBeNull();
    });

    it.each(["unknown", "evil, <script>", "1.2.3.4, 999.1.1.1", ""])(
        "ignores a hop that is not an IP address: %j",
        (value) => {
            expect(forwarded(value)).toBeNull();
        },
    );

    it("accepts IPv6", () => {
        expect(forwarded("6.6.6.6, 2001:db8::1")).toBe("2001:db8::1");
    });

    it("keeps the cookie and protocol", () => {
        const out = upstreamHeaders(new Headers({ cookie: "a=b" }), "https:");
        expect(out.get("cookie")).toBe("a=b");
        expect(out.get("x-forwarded-proto")).toBe("https");
    });
});
