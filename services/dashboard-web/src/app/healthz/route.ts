// Liveness for the container healthcheck and the reverse proxy: no session, no API call, so it
// answers even when `app` is down (proxy.ts leaves this path out of the login redirect).
export const dynamic = "force-dynamic";

export function GET() {
    return new Response("ok", { headers: { "content-type": "text/plain; charset=utf-8" } });
}
