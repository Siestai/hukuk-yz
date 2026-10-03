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
