import { authProxy } from "@hukuk/web-core/lib/auth-proxy";

// Pages only: static assets never reach this function. The API proxy has its own route handler.
export const config = {
    matcher: [
        {
            source: "/((?!api/|healthz$|_next/static|_next/image|favicon.ico).*)",
            missing: [
                { type: "header", key: "next-router-prefetch" },
                { type: "header", key: "purpose", value: "prefetch" },
            ],
        },
    ],
};

export const proxy = authProxy;
