import { useTranslations } from "next-intl";

/** Screen-reader note for a code this UI has no label for (the raw code is shown). */
export function UnknownCode({ known }: { known: boolean }) {
    const t = useTranslations("review.detail");
    return known ? null : <span className="sr-only">{t("unknownCode")}</span>;
}
