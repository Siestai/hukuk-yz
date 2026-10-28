import { describe, expect, it, vi } from "vitest";

import type { CitationRef } from "./chat-types";
import { findQuote, loadSourceText } from "./source-text";

const citation = {
    source_id: "statute:4857:m18",
    category: "statute",
    label: "4857 m.18",
    ref: "4857 m.18",
    review_status: "approved",
    verification: "verified",
    quote: "en  az altı aylık",
} as CitationRef;

function apiReturning(data: unknown) {
    return { GET: vi.fn().mockResolvedValue({ data }) } as never;
}

describe("findQuote", () => {
    it("ignores differences in white space", () => {
        expect(findQuote("işçinin en\naz altı aylık kıdemi", "en az  altı")).toEqual({
            start: 8,
            end: 18,
        });
    });

    it("gives null when the quote is not in the text", () => {
        expect(findQuote("abc", "xyz")).toBeNull();
        expect(findQuote("abc", "  ")).toBeNull();
    });
});

describe("loadSourceText", () => {
    it("shows the article from the knowledge base with the quote highlighted", async () => {
        const text = "İşçinin en az altı aylık kıdemi olmalıdır.";
        const result = await loadSourceText(
            apiReturning({ status: "found", version: { text } }),
            citation,
            "2026-10-01",
        );
        expect(result?.origin).toBe("kb");
        const { start, end } = result!.highlight!;
        expect(text.slice(start, end)).toBe("en az altı aylık");
    });

    it("falls back to the quote when the article is not published", async () => {
        const result = await loadSourceText(
            apiReturning({ status: "not_found" }),
            citation,
            "2026-10-01",
        );
        expect(result).toEqual({
            text: citation.quote,
            highlight: { start: 0, end: citation.quote!.length },
            origin: "quote",
        });
    });

    it("gives null for a source without an endpoint and without a quote", async () => {
        const decision = { ...citation, source_id: "decision:1", quote: null };
        expect(await loadSourceText(apiReturning(undefined), decision, "2026-10-01")).toBeNull();
    });
});
