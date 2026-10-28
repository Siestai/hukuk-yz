"use client";

import { Badge } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { createApiClient } from "@hukuk/web-core/api/client";
import { ACTIVE_SCANS, fileHref, type ReviewStatus, type ScanStatus } from "@/lib/files";
import { ReviewBadge } from "./review-badge";
import { SCAN_REFRESH_LIMIT_MS, SCAN_REFRESH_MS } from "./scan-refresh";
import { ScanBadge } from "./scan-badge";

const linkClass =
    "inline-flex items-center font-medium text-primary underline pointer-coarse:min-h-11";

/**
 * Where an uploaded file stands: "Taranıyor" while the worker scans it (asked for again every 5
 * seconds, for at most 2 minutes, not while the tab is hidden), then "Onay bekliyor" with the way
 * to the approval screen. A scan that ends otherwise shows its own state; one still running when
 * the 2 minutes are over says to look at the file list later instead of spinning on.
 */
export function UploadScan({ fileId }: { fileId: string }) {
    const t = useTranslations("files.upload");
    const [state, setState] = useState<{ scan: ScanStatus; review: ReviewStatus }>({
        scan: "queued",
        review: "pending",
    });
    const [timedOut, setTimedOut] = useState(false);
    const active = ACTIVE_SCANS.includes(state.scan) && !timedOut;

    useEffect(() => {
        if (!active) return;
        const started = Date.now();
        const timer = setInterval(() => {
            if (Date.now() - started >= SCAN_REFRESH_LIMIT_MS) {
                clearInterval(timer);
                setTimedOut(true);
                return;
            }
            if (document.hidden) return;
            void createApiClient()
                .GET("/files/{file_id}", { params: { path: { file_id: fileId } } })
                .then(({ data }) => {
                    if (data) setState({ scan: data.scan_status, review: data.review_status });
                })
                .catch(() => {});
        }, SCAN_REFRESH_MS);
        return () => clearInterval(timer);
    }, [active, fileId]);

    const reviewable = state.scan === "done" && state.review === "pending";
    return (
        <>
            {active ? (
                <Badge>{t("scanning")}</Badge>
            ) : timedOut && ACTIVE_SCANS.includes(state.scan) ? (
                <span className="text-sm text-ink-2">{t("scanTimeout")}</span>
            ) : state.scan === "done" ? (
                <ReviewBadge status={state.review} />
            ) : (
                <ScanBadge status={state.scan} />
            )}
            <Link href={fileHref(fileId)} className={linkClass}>
                {reviewable ? t("reviewNow") : t("openRecord")}
            </Link>
        </>
    );
}
