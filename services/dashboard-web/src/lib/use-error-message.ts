import { useTranslations } from "next-intl";

/** Turns an API error code (or the BFF's `upstream_unavailable`) into its translated message. */
export function useErrorMessage() {
    const t = useTranslations("errors");
    return (code: string | undefined, params: Record<string, unknown> = {}): string => {
        switch (code) {
            case "unauthorized":
                return t("unauthorized");
            case "too_many_attempts": {
                const seconds = Number(params.retry_after);
                return t("too_many_attempts", {
                    minutes: Math.max(1, Math.ceil(Number.isFinite(seconds) ? seconds / 60 : 1)),
                });
            }
            case "validation_error":
                return t("validation_error");
            case "review_conflict":
                return t("review_conflict");
            case "decision_conflict":
                return t("decision_conflict");
            case "bulk_count_changed":
                return t("bulk_count_changed");
            case "bulk_band_not_allowed":
                return t("bulk_band_not_allowed");
            case "extraction_not_found":
                return t("extraction_not_found");
            case "forbidden":
                return t("forbidden");
            case "payload_too_large":
                return t("payload_too_large");
            case "upstream_unavailable":
                return t("upstream_unavailable");
            default:
                return t("generic");
        }
    };
}
