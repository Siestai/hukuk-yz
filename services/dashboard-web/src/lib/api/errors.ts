/** The `{"error": {"code", "params"}}` body of the API (and of the BFF proxy); anything else yields no code. */
export function apiError(body: unknown): { code?: string; params: Record<string, unknown> } {
    const error = (body as { error?: { code?: unknown; params?: unknown } } | null | undefined)
        ?.error;
    return {
        code: typeof error?.code === "string" ? error.code : undefined,
        params:
            error?.params && typeof error.params === "object"
                ? (error.params as Record<string, unknown>)
                : {},
    };
}

/** `app` could not be reached or answered 5xx; the error boundary shows the `upstream_unavailable` message. */
export class UpstreamUnavailableError extends Error {
    constructor(detail: string) {
        super(detail);
        this.name = "UpstreamUnavailableError";
    }
}

/** Server errors reach the client boundary as plain `Error`s in production, so the name is checked, not the class. */
export function isUpstreamUnavailable(error: Error): boolean {
    return error instanceof UpstreamUnavailableError || error.name === "UpstreamUnavailableError";
}
