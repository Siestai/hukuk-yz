const ORIGIN = "http://same-origin.invalid";

const hasControlOrBackslash = (value: string) =>
    [...value].some((char) => char === "\\" || char < " ");

// Login and the stale-session route: returning to them after login would loop or log out.
const isAuthPath = (pathname: string) =>
    pathname === "/oturum-sonu" || pathname.startsWith("/giris");

/** The path to return to after login: a same-origin relative path, else "/". */
export function safeNextPath(raw: string | null | undefined): string {
    if (!raw || !raw.startsWith("/") || raw.startsWith("//") || hasControlOrBackslash(raw)) {
        return "/";
    }
    const url = new URL(raw, ORIGIN);
    if (url.origin !== ORIGIN || isAuthPath(url.pathname) || url.pathname.startsWith("/api/")) {
        return "/";
    }
    return raw;
}
