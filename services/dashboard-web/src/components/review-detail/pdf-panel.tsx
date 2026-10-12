"use client";

import { Button, Dialog } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import type { components } from "@/lib/api/schema";

export type PdfAvailability = components["schemas"]["ReviewDetail"]["pdf"];

/**
 * The original PDF in the browser's viewer. Whether there is one to show comes from the detail
 * (the API checked the path, not the bytes), so the frame is rendered directly; the file route
 * still verifies size and SHA-256, so a late 404 can show inside the frame.
 *
 * Phone browsers mostly cannot show an embedded PDF (iOS shows the first page only), so below `md`
 * the panel is a button instead: the file opens in a window over the page, which still has the
 * "open in a new tab" link as the way out for a browser that cannot show it. The inline frame is
 * still in the markup, hidden, and `loading="lazy"` keeps the browser from fetching a frame
 * nobody can see. On a wide screen the same window enlarges the inline frame.
 */
export function PdfPanel({ src, availability }: { src: string; availability: PdfAvailability }) {
    const t = useTranslations("review.detail.pdf");
    const [open, setOpen] = useState(false);
    // The button that opened the window gets the focus back, also in browsers that do not focus a clicked button.
    const opener = useRef<HTMLElement | null>(null);
    if (availability !== "available") {
        return (
            <p
                role="status"
                className="rounded-md border border-dashed border-border p-6 text-sm text-ink-2"
            >
                {t(availability)}
            </p>
        );
    }
    const show = (button: HTMLElement) => {
        opener.current = button;
        setOpen(true);
    };
    return (
        <>
            <Button
                variant="outline"
                className="w-full md:hidden"
                onClick={(event) => show(event.currentTarget)}
            >
                {t("open")}
            </Button>
            <div className="hidden justify-end md:flex">
                <Button variant="outline" size="sm" onClick={(event) => show(event.currentTarget)}>
                    {t("openLarge")}
                </Button>
            </div>
            <iframe
                title={t("title")}
                src={src}
                loading="lazy"
                className="mt-3 hidden h-viewport w-full rounded-md border border-border md:block"
            />
            <Dialog
                open={open}
                onClose={() => setOpen(false)}
                title={t("title")}
                closeLabel={t("close")}
                variant="viewer"
                returnFocusTo={opener}
            >
                <div className="flex min-h-0 flex-1 flex-col gap-3">
                    <iframe
                        title={t("title")}
                        src={src}
                        className="min-h-0 w-full flex-1 rounded-md border border-border"
                    />
                    <Button asChild variant="outline" className="w-full md:w-auto md:self-end">
                        <a href={src} target="_blank" rel="noopener">
                            {t("newTab")}
                        </a>
                    </Button>
                </div>
            </Dialog>
        </>
    );
}
