import "server-only";

import { headers } from "next/headers";
import createClient from "openapi-fetch";

import { appApiUrl } from "../env";
import { upstreamHeaders } from "../upstream";
import type { paths } from "./schema";

const TIMEOUT_MS = 10_000;

/** Typed client for server components: calls `app` directly with the incoming cookie and client address. */
export async function createServerApi() {
    const incoming = await headers();
    return createClient<paths>({
        baseUrl: appApiUrl(),
        headers: Object.fromEntries(upstreamHeaders(incoming, "http")),
        fetch: (request) => fetch(request, { signal: AbortSignal.timeout(TIMEOUT_MS) }),
    });
}
