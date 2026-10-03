import { type NextRequest, NextResponse } from "next/server";

import { contentSecurityPolicy } from "./lib/security-headers";
import { SESSION_COOKIE } from "./lib/upstream";

// Pages only: static assets never reach this function. The API proxy has its own route handler.
export const config = {
    matcher: [
        {
            source: "/((?!api/|_next/static|_next/image|favicon.ico).*)",
            missing: [
                { type: "header", key: "next-router-prefetch" },
                { type: "header", key: "purpose", value: "prefetch" },
            ],
        },
    ],
};

function redirect(request: NextRequest, location: string, csp: string): NextResponse {
    // Next needs an absolute URL here; resolving against the request's keeps the public host.
    const response = NextResponse.redirect(new URL(location, request.url));
    response.headers.set("Content-Security-Policy", csp);
    return response;
}

/** Cookie presence only: the real check is the API's (the app layout sends a stale session to /giris). */
export function proxy(request: NextRequest): NextResponse {
    const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
    const csp = contentSecurityPolicy(nonce);
    const { pathname, search } = request.nextUrl;
    const signedIn = request.cookies.has(SESSION_COOKIE);

    if (pathname === "/giris" && signedIn) return redirect(request, "/", csp);
    if (pathname !== "/giris" && pathname !== "/oturum-sonu" && !signedIn) {
        const next =
            pathname === "/" && !search ? "" : `?next=${encodeURIComponent(pathname + search)}`;
        return redirect(request, `/giris${next}`, csp);
    }

    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("x-nonce", nonce);
    requestHeaders.set("Content-Security-Policy", csp);
    const response = NextResponse.next({ request: { headers: requestHeaders } });
    response.headers.set("Content-Security-Policy", csp);
    return response;
}
