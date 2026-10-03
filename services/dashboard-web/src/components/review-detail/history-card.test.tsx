import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { HistoryCard } from "./history-card";

const review = {
    id: "r1",
    reviewer_id: "u1",
    reviewer_name: "Baran",
    decision: "edit",
    edits: { decision_date: "2021-03-05", esas_no: "2019/1", mystery: 1 },
    note: "Tarih düzeltildi",
    reviewed_at: "2026-10-02T21:30:00Z",
} as const;

describe("HistoryCard", () => {
    it("says there are no reviews yet", () => {
        renderWithIntl(<HistoryCard reviews={[]} />);
        expect(screen.getByText("Henüz inceleme yok")).toBeInTheDocument();
    });

    it("shows reviewer, decision, Istanbul time, edited field labels and note", () => {
        renderWithIntl(<HistoryCard reviews={[review]} />);
        expect(screen.getByText("Baran")).toBeInTheDocument();
        expect(screen.getByText(/Düzelterek onayladı/)).toBeInTheDocument();
        // 21:30 UTC on 2 October is 00:30 on 3 October in Europe/Istanbul (UTC+3)
        expect(screen.getByText("03.10.2026 00:30")).toHaveAttribute(
            "datetime",
            review.reviewed_at,
        );
        expect(
            screen.getByText(
                `Düzeltilen alanlar: ${messages.fields.decision_date}, ${messages.fields.esas_no}, mystery`,
            ),
        ).toBeInTheDocument();
        expect(screen.getByText("Tarih düzeltildi")).toBeInTheDocument();
    });

    it("names a reviewer without a user account as unknown", () => {
        renderWithIntl(<HistoryCard reviews={[{ ...review, reviewer_name: null }]} />);
        expect(screen.getByText(messages.review.detail.unknownReviewer)).toBeInTheDocument();
    });

    it("shows a rejection without edits", () => {
        renderWithIntl(
            <HistoryCard reviews={[{ ...review, decision: "reject", edits: null, note: null }]} />,
        );
        expect(screen.getByText(/Reddetti/)).toBeInTheDocument();
        expect(screen.queryByText(/Düzeltilen alanlar/)).toBeNull();
    });
});
