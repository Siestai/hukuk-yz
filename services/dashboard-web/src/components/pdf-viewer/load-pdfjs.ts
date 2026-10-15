export type Pdfjs = typeof import("pdfjs-dist");

/**
 * PDF.js is fetched when a viewer opens, not with the page. The worker file is bundled by Next and
 * served from our own origin (`worker-src 'self'`); nothing comes from a CDN.
 */
export async function loadPdfjs(): Promise<Pdfjs> {
    const pdfjs = await import("pdfjs-dist");
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        "pdfjs-dist/build/pdf.worker.min.mjs",
        import.meta.url,
    ).toString();
    return pdfjs;
}
