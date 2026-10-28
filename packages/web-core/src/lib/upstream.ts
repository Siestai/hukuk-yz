import { isIP } from "node:net";

import { trustedProxyHops } from "./env";

export const SESSION_COOKIE = "hukuk_session";

function clientAddress(forwardedFor: string | null): string | undefined {
    const hops = forwardedFor?.split(",") ?? [];
    const client = hops[hops.length - trustedProxyHops()]?.trim();
    return client && isIP(client) ? client : undefined;
}

/**
 * Headers for a request to `app`: the session cookie, and the client address in X-Forwarded-For
 * (the per-IP login limit in `app` reads it).
 *
 * The client is the hop `TRUSTED_PROXY_HOPS` places from the right of the incoming header (default
 * 1: the last entry, the one our edge proxy appended). Entries to the left are supplied by the
 * client and never trusted. Without the header, or when that hop is not an IP address, none is sent.
 */
export function upstreamHeaders(incoming: Headers, protocol: string): Headers {
    const out = new Headers();
    const cookie = incoming.get("cookie");
    if (cookie) out.set("cookie", cookie);
    const client = clientAddress(incoming.get("x-forwarded-for"));
    if (client) out.set("x-forwarded-for", client);
    const proto = incoming.get("x-forwarded-proto")?.split(",")[0]?.trim() || protocol;
    out.set("x-forwarded-proto", proto.replace(/:$/, ""));
    return out;
}
