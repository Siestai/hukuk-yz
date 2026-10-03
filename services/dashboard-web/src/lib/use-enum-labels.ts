import { useMessages, useTranslations } from "next-intl";

/** Display text of API enum values (`enums.*`); unknown values fall back to the raw value. */
export function useEnumLabels() {
    const t = useTranslations();
    const messages = useMessages() as { enums: { reason: Record<string, string> } };
    const label = (group: string, value: string) =>
        t.has(`enums.${group}.${value}`) ? t(`enums.${group}.${value}`) : value;
    return {
        band: (value: string) => label("band", value),
        court: (value: string) => label("court", value === "" ? "unknown" : value),
        reason: (value: string) => label("reason", value),
        isKnownReason: (value: string) => t.has(`enums.reason.${value}`),
        reasonCodes: Object.keys(messages.enums.reason),
    };
}
