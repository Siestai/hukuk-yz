import { useTranslations } from "next-intl";

import { isNumberedArticle } from "@/lib/statute-article";

/** The label of an article number: "m. 18" for a numbered article, "Ek 3" / "Geçici 8" as they are. */
export function useArticleLabel() {
    const t = useTranslations("review.statutes");
    const label = (articleNo: string) =>
        isNumberedArticle(articleNo) ? t("articleNo", { no: articleNo }) : articleNo;
    /** "m. 18 · Heading", or the label alone for an article without a heading. */
    const title = (articleNo: string, heading: string | null) =>
        heading ? t("articleTitle", { article: label(articleNo), heading }) : label(articleNo);
    return { label, title };
}
