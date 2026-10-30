import { apiError } from "./errors";

type Answer<T> = { data?: T; error?: unknown };

/** A failed call of the client: the stable error code of the API (or of the BFF) and its params. */
export class ApiFailure extends Error {
    constructor(
        readonly code: string | undefined,
        readonly params: Record<string, unknown> = {},
    ) {
        super(code ?? "api_failure");
        this.name = "ApiFailure";
    }
}

export async function unwrap<T>(request: Promise<Answer<T>>): Promise<T> {
    const answer = await request.catch(() => {
        throw new ApiFailure("upstream_unavailable");
    });
    if (answer.data === undefined) {
        const { code, params } = apiError(answer.error);
        throw new ApiFailure(code, params);
    }
    return answer.data;
}
