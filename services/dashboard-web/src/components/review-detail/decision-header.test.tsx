import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { renderWithIntl } from "@/test/intl";
import { DecisionHeader } from "./decision-header";

const base = {
    title: "KIDEM TAZMİNATI",
    band: "high",
    score: 100,
    sourceStatus: "analyzed",
    queue: { band: "high", sort: "score_desc", page: 2 },
    source: { origin: "archive", scanned_at: null, journal: null },
} as const;

describe("DecisionHeader", () => {
    it("shows the serif title, band, score and source status", () => {
        renderWithIntl(<DecisionHeader {...base} />);
        const title = screen.getByRole("heading", { level: 1, name: "KIDEM TAZMİNATI" });
        expect(title).toHaveClass("font-serif");
        expect(screen.getByText(messages.enums.band.high)).toBeInTheDocument();
        expect(screen.getByText("100")).toBeInTheDocument();
        expect(screen.getByText(messages.enums.sourceStatus.analyzed)).toBeInTheDocument();
        expect(screen.queryByRole("note")).toBeNull();
    });

    it("links back to the queue with its filters and page", () => {
        renderWithIntl(<DecisionHeader {...base} />);
        expect(screen.getByRole("link", { name: messages.review.detail.back })).toHaveAttribute(
            "href",
            "/?band=high&sort=score_desc&page=2",
        );
    });

    it("leaves the explanation of a record that left the queue to the status strip", () => {
        renderWithIntl(<DecisionHeader {...base} sourceStatus="published" />);
        expect(screen.getByText(messages.enums.sourceStatus.published)).toBeInTheDocument();
        expect(screen.queryByRole("note")).toBeNull();
    });

    it("names the source of a record: the scan with its time and issue, a link to the journal page", () => {
        const journal = { issue_no: 91, page_url: "https://yargi.example.test/karar-1/" };
        renderWithIntl(
            <DecisionHeader
                {...base}
                source={{ origin: "journal_scan", scanned_at: "2026-11-14T08:02:00Z", journal }}
            />,
        );
        expect(screen.getByText("Otomatik tarama, 14.11.2026 11:02, 91. sayı")).toBeInTheDocument();
        const link = screen.getByRole("link", { name: messages.review.detail.source.journalPage });
        expect(link).toHaveAttribute("href", journal.page_url);
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    });

    it("links nothing that is not an http(s) address, and says only the source of an archive record", () => {
        renderWithIntl(
            <DecisionHeader
                {...base}
                source={{
                    origin: "journal_scan",
                    scanned_at: "2026-11-14T08:02:00Z",
                    journal: { issue_no: 91, page_url: "javascript:alert(1)" },
                }}
            />,
        );
        expect(
            screen.queryByRole("link", { name: messages.review.detail.source.journalPage }),
        ).toBeNull();
        document.body.innerHTML = "";
        renderWithIntl(<DecisionHeader {...base} />);
        expect(screen.getByText("Kaynak: Arşiv")).toBeInTheDocument();
    });
});
