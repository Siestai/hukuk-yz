"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { apiError } from "@/lib/api/errors";

type State = { kind: "checking" } | { kind: "ready" } | { kind: "failed"; code?: string };

/**
 * The original PDF in the browser's viewer. The API answers a missing or non-PDF file with a JSON
 * error, which an iframe would show raw, so the URL is fetched first: the frame is only rendered
 * once the answer is a PDF. The probe reads the headers and drops the body (the API does not
 * answer HEAD or Range), so the viewer's own request is the one that downloads the file.
 */
export function PdfPanel({ src }: { src: string }) {
    const t = useTranslations("review.detail.pdf");
    const [state, setState] = useState<State>({ kind: "checking" });
    const [attempt, setAttempt] = useState(0);

    const retry = () => {
        setState({ kind: "checking" });
        setAttempt((n) => n + 1);
    };

    useEffect(() => {
        const controller = new AbortController();
        fetch(src, { signal: controller.signal })
            .then(async (response) => {
                if (response.ok) {
                    await response.body?.cancel();
                    setState({ kind: "ready" });
                    return;
                }
                const { code } = apiError(await response.json().catch(() => null));
                setState({ kind: "failed", code });
            })
            .catch(() => {
                if (!controller.signal.aborted) setState({ kind: "failed" });
            });
        return () => controller.abort();
    }, [src, attempt]);

    if (state.kind === "ready") {
        return (
            <iframe
                title={t("title")}
                src={src}
                className="h-screen w-full rounded-md border border-border"
            />
        );
    }
    if (state.kind === "checking") {
        return (
            <p role="status" className="text-sm text-ink-2">
                {t("checking")}
            </p>
        );
    }
    return (
        <div
            role="alert"
            className="grid justify-items-start gap-3 rounded-md border border-dashed border-border p-6 text-sm text-ink-2"
        >
            <p>
                {state.code === "file_not_found"
                    ? t("file_not_found")
                    : state.code === "file_not_previewable"
                      ? t("file_not_previewable")
                      : t("unavailable")}
            </p>
            {state.code === "file_not_found" || state.code === "file_not_previewable" ? null : (
                <Button variant="outline" onClick={retry}>
                    {t("retry")}
                </Button>
            )}
        </div>
    );
}
