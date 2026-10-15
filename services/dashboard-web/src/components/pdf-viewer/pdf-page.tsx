"use client";

import type { PDFDocumentProxy } from "pdfjs-dist";
import { useEffect, useLayoutEffect, useRef, useState } from "react";

import type { Pdfjs } from "./load-pdfjs";

/** A canvas is capped at twice the CSS pixels: sharp on a phone, without a huge bitmap on a 3x screen. */
const MAX_PIXEL_RATIO = 2;

/** Canvas area cap in device pixels: iOS draws nothing past ~16.7M, and a phone has little memory. */
const MAX_CANVAS_PIXELS = 8_000_000;

/** The canvas pixels per CSS pixel: the screen's ratio, capped, and lowered until the area fits. */
export function outputScale(width: number, height: number, devicePixelRatio: number): number {
    const sharp = Math.min(devicePixelRatio || 1, MAX_PIXEL_RATIO);
    return Math.min(sharp, Math.sqrt(MAX_CANVAS_PIXELS / (width * height)));
}

type PdfPageProps = {
    pdfjs: Pdfjs;
    doc: PDFDocumentProxy;
    number: number;
    /** The CSS width of the page and the height/width ratio to reserve until it is drawn. */
    width: number;
    ratio: number;
    root: HTMLElement | null;
    onError: () => void;
};

/**
 * One page: a placeholder of the right size until it comes near the scrolling box, then the page
 * on a canvas with the selectable text layer over it. Redrawn when the width changes (zoom or a
 * rotated phone). A page far from the box gives its bitmap and text back, keeping its height, and
 * is drawn again when it returns. The element is sized in an effect, because the lint rules forbid inline styles.
 */
export function PdfPage({ pdfjs, doc, number, width, ratio, root, onError }: PdfPageProps) {
    const box = useRef<HTMLDivElement>(null);
    const canvas = useRef<HTMLCanvasElement>(null);
    const text = useRef<HTMLDivElement>(null);
    const [near, setNear] = useState(false);

    useLayoutEffect(() => {
        if (!box.current) return;
        box.current.style.width = `${width}px`;
        box.current.style.height = `${width * ratio}px`;
    }, [width, ratio]);

    useEffect(() => {
        const element = box.current;
        if (!element || !root) return;
        const draw = new IntersectionObserver(
            (entries) => {
                if (entries.some((entry) => entry.isIntersecting)) setNear(true);
            },
            { root, rootMargin: "100% 0px" },
        );
        const release = new IntersectionObserver(
            (entries) => {
                if (entries.every((entry) => !entry.isIntersecting)) setNear(false);
            },
            { root, rootMargin: "300% 0px" },
        );
        draw.observe(element);
        release.observe(element);
        return () => {
            draw.disconnect();
            release.disconnect();
        };
    }, [root]);

    useEffect(() => {
        if (near) return;
        if (canvas.current) {
            canvas.current.width = 0;
            canvas.current.height = 0;
        }
        text.current?.replaceChildren();
    }, [near]);

    useEffect(() => {
        const element = box.current;
        const surface = canvas.current;
        const layer = text.current;
        const context = surface?.getContext("2d");
        if (!near || !element || !surface || !layer || !context) return;
        let cancelled = false;
        let task: ReturnType<Awaited<ReturnType<PDFDocumentProxy["getPage"]>>["render"]> | null =
            null;
        let textLayer: InstanceType<Pdfjs["TextLayer"]> | null = null;
        (async () => {
            const page = await doc.getPage(number);
            const scale = width / page.getViewport({ scale: 1 }).width;
            const viewport = page.getViewport({ scale });
            const pixelRatio = outputScale(
                viewport.width,
                viewport.height,
                window.devicePixelRatio,
            );
            surface.width = Math.floor(viewport.width * pixelRatio);
            surface.height = Math.floor(viewport.height * pixelRatio);
            surface.style.width = `${viewport.width}px`;
            surface.style.height = `${viewport.height}px`;
            element.style.height = `${viewport.height}px`;
            task = page.render({
                canvas: surface,
                canvasContext: context,
                viewport,
                transform: pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0],
            });
            await task.promise;
            if (cancelled) return;
            layer.replaceChildren();
            layer.style.setProperty("--total-scale-factor", String(scale));
            textLayer = new pdfjs.TextLayer({
                textContentSource: page.streamTextContent(),
                container: layer,
                viewport,
            });
            await textLayer.render();
        })().catch((error: unknown) => {
            if (!cancelled && !(error instanceof pdfjs.RenderingCancelledException)) onError();
        });
        return () => {
            cancelled = true;
            task?.cancel();
            textLayer?.cancel();
        };
    }, [near, pdfjs, doc, number, width, onError]);

    return (
        <div
            ref={box}
            data-page={number}
            className="relative mx-auto shrink-0 overflow-hidden rounded-sm border border-border bg-surface"
        >
            <canvas ref={canvas} className="block" />
            <div ref={text} className="textLayer" />
        </div>
    );
}
