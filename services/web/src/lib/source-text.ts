import type { createApiClient } from "@hukuk/web-core/api/client";

import type { CitationRef } from "./chat-types";

type Api = ReturnType<typeof createApiClient>;

/** What the viewer shows: the text, and the part of it the answer relies on (if it was found). */
export type SourceText = {
    text: string;
    highlight: { start: number; end: number } | null;
    /** `kb`: the full text from the knowledge base; `quote`: only the quoted part the answer carries. */
    origin: "kb" | "quote";
};

const STATUTE_ID = /^statute:(\d+):m(.+)$/;

/** Where `quote` sits in `text`, ignoring differences in white space; null when it is not there. */
export function findQuote(text: string, quote: string): { start: number; end: number } | null {
    const words = quote.split(/\s+/).filter(Boolean);
    if (words.length === 0) return null;
    const escaped = words.map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    const match = new RegExp(escaped.join("\\s+")).exec(text);
    return match ? { start: match.index, end: match.index + match[0].length } : null;
}

function highlightOf(text: string, citation: CitationRef): SourceText["highlight"] {
    const { char_start: start, char_end: end, quote } = citation;
    if (start != null && end != null && end <= text.length) return { start, end };
    return quote ? findQuote(text, quote) : null;
}

/**
 * The full text of a statute article from the knowledge base (`GET /statutes/{number}/articles`,
 * the text in force on `asOf`); any other source, or an article the knowledge base does not
 * publish (yet), shows the quote the answer carries. Null when there is no text at all.
 */
export async function loadSourceText(
    api: Api,
    citation: CitationRef,
    asOf: string,
): Promise<SourceText | null> {
    const statute = STATUTE_ID.exec(citation.source_id);
    if (statute) {
        const [, number = "", article = ""] = statute;
        const { data } = await api
            .GET("/statutes/{number}/articles/{article_no}", {
                params: { path: { number, article_no: article }, query: { as_of: asOf } },
            })
            .catch(() => ({ data: undefined }));
        const text = data?.status === "found" ? data.version?.text : undefined;
        if (text) return { text, highlight: highlightOf(text, citation), origin: "kb" };
    }
    if (!citation.quote) return null;
    return {
        text: citation.quote,
        highlight: { start: 0, end: citation.quote.length },
        origin: "quote",
    };
}
