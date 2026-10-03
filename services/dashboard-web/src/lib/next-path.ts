const ORIGIN = "http://same-origin.invalid";

const hasControlOrBackslash = (value: string) =>
    [...value].some((char) => char === "\\" || char < " ");

/** The path to return to after login: a same-origin relative path, else "/". */
export function safeNextPath(raw: string | null | undefined): string {
    if (!raw || !raw.startsWith("/") || raw.startsWith("//") || hasControlOrBackslash(raw)) {
        return "/";
    }
    const url = new URL(raw, ORIGIN);
    if (url.origin !== ORIGIN || url.pathname === "/giris" || url.pathname.startsWith("/api/")) {
        return "/";
    }
    return raw;
}
