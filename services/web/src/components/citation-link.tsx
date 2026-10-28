"use client";

import { Badge } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { CitationRef } from "@/lib/chat-types";

/** A source as a bold link on its own line; tapping opens its text. The state of the source shows beside it. */
export function CitationLink({
    citation,
    onOpen,
}: {
    citation: CitationRef;
    onOpen: (citation: CitationRef) => void;
}) {
    const t = useTranslations("chat.citation");
    return (
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <button
                type="button"
                onClick={() => onOpen(citation)}
                aria-label={t("open", { label: citation.label })}
                className="inline-flex min-h-8 items-center text-left font-sans text-sm font-semibold text-primary underline decoration-primary/40 underline-offset-4 focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:min-h-11"
            >
                {citation.label}
            </button>
            {citation.verification === "verified" ? (
                <Badge variant="high">{t("verified")}</Badge>
            ) : null}
            {citation.verification === "unverified" ? (
                <Badge variant="medium">{t("unverified")}</Badge>
            ) : null}
            {citation.review_status === "analyzed" ? (
                <Badge variant="medium">{t("analyzed")}</Badge>
            ) : null}
        </span>
    );
}
