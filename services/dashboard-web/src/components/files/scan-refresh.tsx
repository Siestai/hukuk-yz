"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export const SCAN_REFRESH_MS = 5_000;
export const SCAN_REFRESH_LIMIT_MS = 120_000;

/**
 * While a scan is queued or running (`active`) the page asks the server for fresh data every
 * 5 seconds, for at most 2 minutes (not while the tab is hidden); the status badge then turns by itself. Renders nothing.
 */
export function ScanRefresh({ active }: { active: boolean }) {
    const router = useRouter();
    useEffect(() => {
        if (!active) return;
        const started = Date.now();
        const timer = setInterval(() => {
            if (Date.now() - started >= SCAN_REFRESH_LIMIT_MS) clearInterval(timer);
            else if (!document.hidden) router.refresh();
        }, SCAN_REFRESH_MS);
        return () => clearInterval(timer);
    }, [active, router]);
    return null;
}
