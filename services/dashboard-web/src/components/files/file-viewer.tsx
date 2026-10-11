import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { contentUrl } from "@/lib/files";

/**
 * "Dosyayı aç": the stored file in a new tab (a PDF shows in the viewer, other types download).
 * A PDF is also embedded from `md`; phone browsers mostly cannot show an embedded PDF, so the
 * frame stays hidden there and `loading="lazy"` keeps the browser from fetching it.
 */
export function FileViewer({ fileId, pdf }: { fileId: string; pdf: boolean }) {
    const t = useTranslations("files.detail.viewer");
    const src = contentUrl(fileId);
    return (
        <div className="grid gap-4">
            <Button asChild variant="outline" className="w-full md:w-fit">
                <a href={src} target="_blank" rel="noopener">
                    {t("open")}
                </a>
            </Button>
            {pdf ? (
                <iframe
                    title={t("title")}
                    src={src}
                    loading="lazy"
                    className="hidden h-viewport w-full rounded-md border border-border md:block"
                />
            ) : null}
        </div>
    );
}
