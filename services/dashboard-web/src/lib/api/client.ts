import createClient from "openapi-fetch";

import type { paths } from "./schema";

export function createApiClient() {
    return createClient<paths>({ baseUrl: "/api", credentials: "same-origin" });
}
