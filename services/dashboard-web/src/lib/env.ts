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
