"use client";

import { Button, Skeleton } from "@hukuk/ui";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { loadPdfjs, type Pdfjs } from "./load-pdfjs";
import { PdfPage } from "./pdf-page";

/** Zoom steps of the +/- buttons, as a share of the width that fits the screen. */
export const ZOOM_STEPS = [1, 1.25, 1.5, 2, 3] as const;

type Loaded = { pdfjs: Pdfjs; doc: PDFDocumentProxy; ratio: number };

/**
 * A PDF drawn page by page on canvases, because phone browsers cannot show an embedded PDF (Android
 * Chrome has no viewer, iOS shows the first page). The pages are stacked and fit the width; the
 * zoom buttons widen them and the box scrolls both ways. A page is drawn only when it nears the
 * box. It is mounted only while its window is open, which is when PDF.js is loaded. When the file
 * cannot be read or drawn, a message and the "open in a new tab" link take its place.
 */
export function PdfViewer({ src }: { src: string }) {
    const t = useTranslations("pdfViewer");
    const [loaded, setLoaded] = useState<Loaded | null>(null);
    const [failed, setFailed] = useState(false);
    const [scroller, setScroller] = useState<HTMLDivElement | null>(null);
    const [fitWidth, setFitWidth] = useState(0);
    const [step, setStep] = useState(0);
    const fail = useCallback(() => setFailed(true), []);

    useEffect(() => {
        let cancelled = false;
        let destroy: (() => Promise<void>) | null = null;
        (async () => {
            const pdfjs = await loadPdfjs();
            const task = pdfjs.getDocument({ url: src });
            destroy = () => task.destroy();
            const doc = await task.promise;
            const first = (await doc.getPage(1)).getViewport({ scale: 1 });
            if (!cancelled) setLoaded({ pdfjs, doc, ratio: first.height / first.width });
        })().catch(() => {
            if (!cancelled) setFailed(true);
        });
        return () => {
            cancelled = true;
            void destroy?.();
        };
    }, [src]);

    useEffect(() => {
        if (!scroller) return;
        const measure = () => setFitWidth(scroller.clientWidth);
        measure();
        const observer = new ResizeObserver(measure);
        observer.observe(scroller);
        return () => observer.disconnect();
    }, [scroller]);

    const zoom = ZOOM_STEPS[step] ?? 1;
    const width = Math.max(fitWidth - 2, 0) * zoom;
    const newTab = (
        <Button asChild variant="outline" className="w-full md:w-auto">
            <a href={src} target="_blank" rel="noopener">
                {t("newTab")}
            </a>
        </Button>
    );

    if (failed) {
        return (
            <div className="grid content-start gap-3">
                <p role="alert" className="text-sm text-ink-2">
                    {t("failed")}
                </p>
                {newTab}
            </div>
        );
    }
    return (
        <div className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="flex items-center gap-2">
                <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t("zoomOut")}
                    disabled={step === 0}
                    onClick={() => setStep(step - 1)}
                >
                    <span aria-hidden="true">−</span>
                </Button>
                <output aria-label={t("zoom")} className="min-w-12 text-center text-sm text-ink-2">
                    {Math.round(zoom * 100)}%
                </output>
                <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    aria-label={t("zoomIn")}
                    disabled={step === ZOOM_STEPS.length - 1}
                    onClick={() => setStep(step + 1)}
                >
                    <span aria-hidden="true">+</span>
                </Button>
            </div>
            <div
                ref={setScroller}
                role="region"
                aria-label={t("pages")}
                aria-busy={!loaded}
                tabIndex={0}
                className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto overscroll-contain rounded-md border border-border bg-sunken p-px"
            >
                {loaded ? (
                    Array.from({ length: loaded.doc.numPages }, (_, index) => (
                        <PdfPage
                            key={index}
                            pdfjs={loaded.pdfjs}
                            doc={loaded.doc}
                            number={index + 1}
                            width={width}
                            ratio={loaded.ratio}
                            root={scroller}
                            onError={fail}
                        />
                    ))
                ) : (
                    <Skeleton role="status" aria-label={t("loading")} className="h-full min-h-48" />
                )}
            </div>
            {newTab}
        </div>
    );
}
