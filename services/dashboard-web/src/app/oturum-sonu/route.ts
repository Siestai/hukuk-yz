import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/upstream";

// Where the app layout sends a session the API no longer accepts: drops the stale cookie
// (otherwise proxy.ts would bounce /giris back to /) and goes to the login page.
export function GET() {
    const response = new NextResponse(null, { status: 307, headers: { location: "/giris" } });
    response.cookies.delete(SESSION_COOKIE);
    return response;
}
