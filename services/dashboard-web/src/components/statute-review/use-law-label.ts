import { useTranslations } from "next-intl";

import { isLawNumber } from "@/lib/statute-timeline";

/** "6552 sayılı Kanun" for a law number; the Constitutional Court ("AYM") and the like as they are. */
export function useLawLabel() {
    const t = useTranslations("review.statutes");
    return (law: string) => (isLawNumber(law) ? t("law", { law }) : law);
}
