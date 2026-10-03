import { useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";

export type PdfAvailability = components["schemas"]["ReviewDetail"]["pdf"];

/**
 * The original PDF in the browser's viewer. Whether there is one to show comes from the detail
 * (the API checked the path, not the bytes), so the frame is rendered directly; the file route
 * still verifies size and SHA-256, so a late 404 can show inside the frame.
 */
export function PdfPanel({ src, availability }: { src: string; availability: PdfAvailability }) {
    const t = useTranslations("review.detail.pdf");
    if (availability === "available") {
        return (
            <iframe
                title={t("title")}
                src={src}
                className="h-screen w-full rounded-md border border-border"
            />
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
