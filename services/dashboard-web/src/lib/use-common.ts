import { useTranslations } from "next-intl";

/** Placeholders shared by every screen: the marker of an empty value and the separator of inline parts. */
export function useCommon() {
    const t = useTranslations("common");
    return { empty: t("empty"), separator: t("separator") };
}
