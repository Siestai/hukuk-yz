// Fail at startup, not on the first request, when the server is misconfigured.
export async function register() {
    if (process.env.NEXT_RUNTIME === "nodejs") {
        const { appApiUrl } = await import("./lib/env");
        appApiUrl();
    }
}
