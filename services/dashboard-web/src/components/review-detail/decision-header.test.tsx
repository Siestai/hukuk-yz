import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { DecisionHeader } from "./decision-header";

const base = {
    title: "KIDEM TAZMİNATI",
    band: "high",
    score: 100,
    sourceStatus: "analyzed",
    queue: { band: "high", sort: "score_desc", page: 2 },
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
});
