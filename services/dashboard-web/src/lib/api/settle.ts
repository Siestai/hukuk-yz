import { redirect } from "next/navigation";

import { apiError, UpstreamUnavailableError } from "./errors";

type Answer<T> = { data?: T; error?: unknown; response: Response };

export type Settled<T> =
    { data: T; error?: undefined } | { error: ReturnType<typeof apiError>; data?: undefined };

/** The data of a 2xx answer, or the API's error body of a 4xx; a lost session or a server failure throws. */
export async function settle<T>(request: Promise<Answer<T>>, what: string): Promise<Settled<T>> {
    const answer = await request.catch((cause: unknown) => {
        throw new UpstreamUnavailableError(`${what} failed: ${String(cause)}`);
    });
    const { status } = answer.response;
    if (status === 401) redirect("/oturum-sonu");
    if (status >= 500) throw new UpstreamUnavailableError(`${what} answered ${status}`);
    if (answer.data === undefined) return { error: apiError(answer.error) };
    return { data: answer.data };
}
