// Liveness for the container healthcheck and the reverse proxy: no session, no API call, so it
// answers even when `app` is down (the page proxy leaves this path out of the login redirect).
export function GET() {
    return new Response("ok", { headers: { "content-type": "text/plain; charset=utf-8" } });
}
