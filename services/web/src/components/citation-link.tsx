"use client";

import { Badge } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { CitationRef } from "@/lib/chat-types";

/** A source as a chip; tapping opens its text. The state of the source shows inside the chip. */
export function CitationLink({
    citation,
    onOpen,
}: {
    citation: CitationRef;
    onOpen: (citation: CitationRef) => void;
}) {
    const t = useTranslations("chat.citation");
    return (
        <button
            type="button"
            onClick={() => onOpen(citation)}
            aria-label={t("open", { label: citation.label })}
            className="lip lip-edge mb-0.5 inline-flex min-h-11 max-w-full flex-wrap items-center gap-2 rounded-md border border-primary-edge bg-primary-soft px-3 py-1 text-left font-sans text-sm font-semibold text-high focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        >
            <span className="wrap-anywhere">{citation.label}</span>
            {citation.verification === "verified" ? (
                <Badge variant="high" className="bg-surface">
                    {t("verified")}
                </Badge>
            ) : null}
            {citation.verification === "unverified" ? (
                <Badge variant="medium">{t("unverified")}</Badge>
            ) : null}
            {citation.review_status === "analyzed" ? (
                <Badge variant="medium">{t("analyzed")}</Badge>
            ) : null}
        </button>
    );
}
