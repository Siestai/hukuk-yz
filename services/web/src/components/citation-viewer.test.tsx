import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CitationRef } from "@/lib/chat-types";
import { loadSourceText } from "@/lib/source-text";
import { renderWithIntl } from "@/test/intl";
import { CitationViewer } from "./citation-viewer";

vi.mock("@/lib/source-text", () => ({ loadSourceText: vi.fn() }));

const citation = {
    source_id: "statute:4857:m18",
    category: "statute",
    label: "4857 m.18",
    ref: "4857 m.18",
    review_status: "approved",
    verification: "verified",
    quote: "en az altı",
    used_for: "Kıdem şartı",
    valid_from: "2020-01-01",
} as CitationRef;

beforeEach(() => {
    vi.mocked(loadSourceText).mockReset();
    Element.prototype.scrollIntoView = vi.fn();
});

describe("CitationViewer", () => {
    it("shows the text with the relied-on part marked, and the review status", async () => {
        vi.mocked(loadSourceText).mockResolvedValue({
            text: "İşçinin en az altı aylık kıdemi olmalıdır.",
            highlight: { start: 8, end: 18 },
            origin: "kb",
        });
        renderWithIntl(<CitationViewer citation={citation} asOf="2026-10-01" />);
        expect(await screen.findByText("en az altı")).toHaveProperty("tagName", "MARK");
        expect(screen.getByText("Onaylı metin")).toBeInTheDocument();
        expect(screen.getByText("Teyitli")).toBeInTheDocument();
        expect(screen.getByText("Cevaptaki kullanım: Kıdem şartı")).toBeInTheDocument();
        expect(loadSourceText).toHaveBeenCalledWith(expect.anything(), citation, "2026-10-01");
        expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: "center" });
    });

    it("says so when the quote is all there is", async () => {
        vi.mocked(loadSourceText).mockResolvedValue({
            text: "en az altı",
            highlight: { start: 0, end: 10 },
            origin: "quote",
        });
        renderWithIntl(<CitationViewer citation={citation} asOf="2026-10-01" />);
        expect(
            await screen.findByText("Kaynağın yalnız cevapta kullanılan kısmı gösteriliyor."),
        ).toBeInTheDocument();
    });

    it("shows that an unapproved, unverified source is", async () => {
        vi.mocked(loadSourceText).mockResolvedValue(null);
        renderWithIntl(
            <CitationViewer
                citation={{ ...citation, review_status: "analyzed", verification: "unverified" }}
                asOf="2026-10-01"
            />,
        );
        expect(screen.getByText("Onaylanmadı")).toBeInTheDocument();
        expect(screen.getByText("Teyitsiz")).toBeInTheDocument();
        expect(
            await screen.findByText("Bu dayanağın metni şu an gösterilemiyor."),
        ).toBeInTheDocument();
    });
});
