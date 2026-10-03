export const SESSION_COOKIE = "hukuk_session";

/**
 * Headers for a request to `app`: the session cookie, and the client address in X-Forwarded-For
 * (the per-IP login limit in `app` reads it).
 *
 * The first hop of the incoming X-Forwarded-For is taken as the client. That is only true when the
 * edge proxy in front of this server overwrites the header instead of appending to it; a client
 * could otherwise pick its own address and dodge the limit.
 */
export function upstreamHeaders(incoming: Headers, protocol: string): Headers {
    const out = new Headers();
    const cookie = incoming.get("cookie");
    if (cookie) out.set("cookie", cookie);
    const client = incoming.get("x-forwarded-for")?.split(",")[0]?.trim();
    if (client) out.set("x-forwarded-for", client);
    const proto = incoming.get("x-forwarded-proto")?.split(",")[0]?.trim() || protocol;
    out.set("x-forwarded-proto", proto.replace(/:$/, ""));
    return out;
}
