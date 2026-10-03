import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { DuplicatesCard } from "./duplicates-card";

const duplicate = { extraction_id: "d1", band: "medium", score: 75, text_length: 12345 } as const;

describe("DuplicatesCard", () => {
    it("renders nothing without duplicates", () => {
        const { container } = renderWithIntl(
            <DuplicatesCard duplicates={[]} queue={{ sort: "score_asc", page: 1 }} />,
        );
        expect(container).toBeEmptyDOMElement();
    });

    it("shows band, score and text length, and links to the other record with the queue state", () => {
        renderWithIntl(
            <DuplicatesCard
                duplicates={[duplicate]}
                queue={{ band: "low", sort: "score_asc", page: 1 }}
            />,
        );
        expect(screen.getByText(messages.review.detail.duplicates.title)).toBeInTheDocument();
        expect(screen.getByText(messages.enums.band.medium)).toBeInTheDocument();
        expect(screen.getByText("75")).toBeInTheDocument();
        const link = screen.getByRole("link", { name: "Metin uzunluğu 12.345 karakter" });
        expect(link).toHaveAttribute("href", "/kararlar/d1?band=low");
    });
});
