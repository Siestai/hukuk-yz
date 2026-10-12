import { cn, Label } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { Suggestion, SuggestionField } from "@/lib/file-suggestions";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

/**
 * One field of the approval form with the control passed as `children`, and under it where the
 * value came from. A value the user changed is theirs ("Siz girdiniz"), so the quote of the
 * original suggestion goes away; an LLM suggestion nothing in the text supports gets a warning.
 */
export function ApprovalField({
    id,
    label,
    field,
    suggestion,
    value,
    className,
    children,
}: {
    id: string;
    label: string;
    field?: SuggestionField;
    suggestion?: Suggestion;
    /** What the control holds now. */
    value: string;
    className?: string;
    children: ReactNode;
}) {
    const t = useTranslations("files.detail.approve");
    const labels = useEnumLabels();
    const { date } = useDates();
    const edited = suggestion !== undefined && value !== suggestion.value;
    const source = suggestion ? (edited ? "user" : suggestion.source) : undefined;
    const quote = suggestion && !edited ? suggestion.quote : null;
    const detected = suggestion?.detected;
    const show = (text: string) =>
        field === "doc_type" ? labels.docType(text) : field === "doc_date" ? date(text) : text;

    return (
        <div className={cn("grid gap-1.5", className)}>
            <Label htmlFor={id}>{label}</Label>
            {children}
            {source ? (
                <p className="text-xs wrap-anywhere text-ink-2">
                    <span className="font-medium">{labels.suggestionSource(source)}</span>
                    {quote ? ` · ${t("evidence", { page: quote.page, quote: quote.text })}` : null}
                </p>
            ) : null}
            {suggestion?.unsupported && !edited ? (
                <p role="note" className="text-xs text-medium">
                    {t("unsupported")}
                </p>
            ) : null}
            {detected && detected.value !== value ? (
                <p className="text-xs wrap-anywhere text-ink-2">
                    {t("detected", { value: show(detected.value) })}
                </p>
            ) : null}
        </div>
    );
}
