const dev = () => process.env.NODE_ENV === "development";

/**
 * Content-Security-Policy for one response. Scripts run only with the per-request nonce
 * (Next applies it to its own scripts); styles allow 'unsafe-inline' because Next and the UI
 * components emit inline style. The PDF.js viewer runs its worker from our own origin, which
 * `worker-src` must name: without it a worker falls back to `script-src`, where 'strict-dynamic'
 * ignores 'self'. Development adds what HMR and React's debug eval need.
 */
export function contentSecurityPolicy(nonce: string, isDev = dev()): string {
    return [
        "default-src 'self'",
        `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        `connect-src 'self'${isDev ? " ws: wss:" : ""}`,
        "frame-src 'self'",
        "worker-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ].join("; ");
}

/** Headers that do not vary per request; the CSP is set in proxy.ts. */
export function staticSecurityHeaders(isDev = dev()): { key: string; value: string }[] {
    return [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "same-origin" },
        {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
        },
        { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]),
    ];
}

/** Framing headers of an `/api` response: pages get theirs from the CSP in proxy.ts. */
export function frameHeaders(sameOriginMayFrame: boolean): Record<string, string> {
    return {
        "Content-Security-Policy": `frame-ancestors ${sameOriginMayFrame ? "'self'" : "'none'"}`,
        "X-Frame-Options": sameOriginMayFrame ? "SAMEORIGIN" : "DENY",
    };
}
