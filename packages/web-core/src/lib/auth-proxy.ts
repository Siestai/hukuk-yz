import { type NextRequest, NextResponse } from "next/server";

import { contentSecurityPolicy } from "./security-headers";
import { SESSION_COOKIE } from "./upstream";

function redirect(request: NextRequest, location: string, csp: string): NextResponse {
    // Next needs an absolute URL here; resolving against the request's keeps the public host.
    const response = NextResponse.redirect(new URL(location, request.url));
    response.headers.set("Content-Security-Policy", csp);
    return response;
}

/**
 * The page proxy of both apps (each app's proxy.ts owns the `config` matcher, which Next reads
 * statically). Cookie presence only: the real check is the API's (the app layout sends a stale
 * session to /giris).
 */
export function authProxy(request: NextRequest): NextResponse {
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
