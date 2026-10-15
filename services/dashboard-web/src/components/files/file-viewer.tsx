"use client";

import { Button, Dialog } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { PdfViewer } from "@/components/pdf-viewer/pdf-viewer";
import { contentUrl } from "@/lib/files";

/**
 * "Dosyayı aç": the stored file in a new tab (a PDF shows in the viewer, other types download).
 * A PDF is also embedded from `md`. Phone browsers mostly cannot show an embedded PDF, so there
 * the frame stays hidden (`loading="lazy"` keeps the browser from fetching it) and the button
 * opens a window over the page in which PDF.js draws the pages.
 */
export function FileViewer({ fileId, pdf }: { fileId: string; pdf: boolean }) {
    const t = useTranslations("files.detail.viewer");
    const src = contentUrl(fileId);
    const [open, setOpen] = useState(false);
    // The button that opened the window gets the focus back, also in browsers that do not focus a clicked button.
    const opener = useRef<HTMLElement | null>(null);
    const newTab = (className: string) => (
        <Button asChild variant="outline" className={className}>
            <a href={src} target="_blank" rel="noopener">
                {t("open")}
            </a>
        </Button>
    );
    if (!pdf) return <div className="grid gap-4">{newTab("w-full md:w-fit")}</div>;
    return (
        <div className="grid gap-4">
            <Button
                variant="outline"
                className="w-full md:hidden"
                onClick={(event) => {
                    opener.current = event.currentTarget;
                    setOpen(true);
                }}
            >
                {t("open")}
            </Button>
            {newTab("hidden w-fit md:inline-flex")}
            <iframe
                title={t("title")}
                src={src}
                loading="lazy"
                className="hidden h-viewport w-full rounded-md border border-border md:block"
            />
            <Dialog
                open={open}
                onClose={() => setOpen(false)}
                title={t("title")}
                closeLabel={t("close")}
                variant="viewer"
                returnFocusTo={opener}
            >
                <PdfViewer src={src} />
            </Dialog>
        </div>
    );
}
