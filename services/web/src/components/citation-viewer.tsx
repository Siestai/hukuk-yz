"use client";

import { Badge } from "@hukuk/ui";
import { createApiClient } from "@hukuk/web-core/api/client";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";

import type { CitationRef } from "@/lib/chat-types";
import { loadSourceText, type SourceText } from "@/lib/source-text";

type Loaded = { citation: CitationRef; asOf: string; source: SourceText | null };

/**
 * The full text of a source with the part the answer relies on highlighted and scrolled into
 * view; whether it is approved and verified shows above the text.
 */
export function CitationViewer({ citation, asOf }: { citation: CitationRef; asOf: string }) {
    const t = useTranslations("chat.viewer");
    const format = useFormatter();
    const api = useMemo(() => createApiClient(), []);
    const [loaded, setLoaded] = useState<Loaded | null>(null);
    const mark = useRef<HTMLElement>(null);

    useEffect(() => {
        let current = true;
        void loadSourceText(api, citation, asOf).then((source) => {
            if (current) setLoaded({ citation, asOf, source });
        });
        return () => {
            current = false;
        };
    }, [api, citation, asOf]);

    useEffect(() => {
        mark.current?.scrollIntoView?.({ block: "center" });
    }, [loaded]);

    const source =
        loaded?.citation === citation && loaded.asOf === asOf ? loaded.source : undefined;
    const date = (value: string) => format.dateTime(new Date(value), "date");
    const { valid_from: from, valid_to: to } = citation;

    return (
        <div className="grid gap-3">
            <h3 className="wrap-anywhere font-serif text-xl font-semibold text-ink">
                {citation.label}
            </h3>
            <div className="flex flex-wrap gap-2">
                <Badge variant={citation.review_status === "approved" ? "high" : "medium"}>
                    {t(citation.review_status)}
                </Badge>
                <Badge variant={citation.verification === "verified" ? "high" : "medium"}>
                    {t(citation.verification === "verified" ? "verified" : "unverified")}
                </Badge>
            </div>
            {from ? (
                <p className="text-sm text-ink-2">
                    {to
                        ? t("validity", { from: date(from), to: date(to) })
                        : t("validityOpen", { from: date(from) })}
                </p>
            ) : null}
            {source === undefined ? (
                <p role="status" className="text-sm text-ink-2">
                    {t("loading")}
                </p>
            ) : source === null ? (
                <p role="status" className="text-sm text-ink-2">
                    {t("unavailable")}
                </p>
            ) : (
                <>
                    <p className="wrap-anywhere whitespace-pre-line font-serif text-lg leading-relaxed text-ink-2">
                        {source.highlight ? (
                            <>
                                {source.text.slice(0, source.highlight.start)}
                                <mark ref={mark} className="bg-accent/30 text-ink">
                                    {source.text.slice(
                                        source.highlight.start,
                                        source.highlight.end,
                                    )}
                                </mark>
                                {source.text.slice(source.highlight.end)}
                            </>
                        ) : (
                            source.text
                        )}
                    </p>
                    {source.origin === "quote" ? (
                        <p className="text-sm text-ink-3">{t("quoteOnly")}</p>
                    ) : null}
                </>
            )}
            {citation.used_for ? (
                <p className="rounded-md bg-primary-soft px-3 py-2 text-sm text-primary">
                    {t("usedFor", { text: citation.used_for })}
                </p>
            ) : null}
        </div>
    );
}
