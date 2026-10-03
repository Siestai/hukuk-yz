import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/upstream";

// A GET by design: it is the target of a server redirect from the app layout, so it cannot be a POST.
// It only clears this client's own cookie; a cross-site link to it can at most force a new login.
// Where the app layout sends a session the API no longer accepts: drops the stale cookie
// (otherwise proxy.ts would bounce /giris back to /) and goes to the login page.
export function GET() {
    const response = new NextResponse(null, { status: 307, headers: { location: "/giris" } });
    response.cookies.delete(SESSION_COOKIE);
    return response;
}
