import { useMessages, useTranslations } from "next-intl";

/** Display text of API enum values (`enums.*`); unknown values fall back to the raw value. */
export function useEnumLabels() {
    const t = useTranslations();
    const messages = useMessages() as { enums: { reason: Record<string, string> } };
    const label = (group: string, value: string) =>
        t.has(`enums.${group}.${value}`) ? t(`enums.${group}.${value}`) : value;
    // A warning may carry a detail after a colon ("multiple_esas_candidates:2010/1").
    const warningCode = (value: string) => value.split(":", 1)[0] ?? value;
    return {
        band: (value: string) => label("band", value),
        court: (value: string) => label("court", value === "" ? "unknown" : value),
        courtLevel: (value: string) => label("courtLevel", value),
        outcome: (value: string) => label("outcome", value),
        sourceStatus: (value: string) => label("sourceStatus", value),
        reason: (value: string) => label("reason", value),
        isKnownReason: (value: string) => t.has(`enums.reason.${value}`),
        warning: (value: string) => {
            const detail = value.slice(warningCode(value).length);
            return `${label("warning", warningCode(value))}${detail}`;
        },
        isKnownWarning: (value: string) => t.has(`enums.warning.${warningCode(value)}`),
        reasonCodes: Object.keys(messages.enums.reason),
    };
}
