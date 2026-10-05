import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";

export type PdfAvailability = components["schemas"]["ReviewDetail"]["pdf"];

/**
 * The original PDF in the browser's viewer. Whether there is one to show comes from the detail
 * (the API checked the path, not the bytes), so the frame is rendered directly; the file route
 * still verifies size and SHA-256, so a late 404 can show inside the frame.
 *
 * Phone browsers mostly cannot show an embedded PDF (iOS shows the first page only), so below `md`
 * the panel is a link that opens the file in a new tab. The frame is still in the markup, hidden,
 * and `loading="lazy"` keeps the browser from fetching a frame nobody can see.
 */
export function PdfPanel({ src, availability }: { src: string; availability: PdfAvailability }) {
    const t = useTranslations("review.detail.pdf");
    if (availability === "available") {
        return (
            <>
                <Button asChild variant="outline" className="w-full md:hidden">
                    <a href={src} target="_blank" rel="noopener">
                        {t("open")}
                    </a>
                </Button>
                <iframe
                    title={t("title")}
                    src={src}
                    loading="lazy"
                    className="hidden h-viewport w-full rounded-md border border-border md:block"
                />
            </>
        );
    }
    return (
        <p
            role="status"
            className="rounded-md border border-dashed border-border p-6 text-sm text-ink-2"
        >
            {t(availability)}
        </p>
    );
}
