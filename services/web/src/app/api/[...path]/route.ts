import { createApiProxy } from "@hukuk/web-core/lib/api-proxy";
import { frameHeaders } from "@hukuk/web-core/lib/security-headers";

// The chat, the login and the statute article the basis viewer reads; nothing is framed.
const forward = createApiProxy({
    allowedPrefixes: ["auth/", "chat/", "statutes/"],
    frameHeaders: () => frameHeaders(false),
});

export const GET = forward;
export const POST = forward;
