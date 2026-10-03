/** Base URL of the `app` API (server only; never sent to the browser). */
export function appApiUrl(): string {
    const url = process.env.APP_API_URL?.trim();
    if (!url) {
        throw new Error(
            "APP_API_URL is not set (e.g. http://localhost:8000 for local development).",
        );
    }
    try {
        new URL(url);
    } catch {
        throw new Error(`APP_API_URL is not a valid URL: ${url}`);
    }
    return url.replace(/\/+$/, "");
}

/**
 * How many proxies in front of this server append to X-Forwarded-For (server only). The client
 * address is the hop that many places from the right of the incoming header. Default 1: only
 * the edge proxy, whose entry is the last one.
 */
export function trustedProxyHops(): number {
    const raw = process.env.TRUSTED_PROXY_HOPS?.trim();
    if (!raw) return 1;
    const hops = Number(raw);
    if (!/^\d+$/.test(raw) || hops < 1) {
        throw new Error(`TRUSTED_PROXY_HOPS must be a positive integer: ${raw}`);
    }
    return hops;
}
