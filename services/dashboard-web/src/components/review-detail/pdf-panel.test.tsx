import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { PdfPanel } from "./pdf-panel";

const SRC = "/api/review/decisions/d1/file";

describe("PdfPanel", () => {
    it("renders the titled iframe straight away when the PDF is available", () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        expect(screen.getByTitle(messages.review.detail.pdf.title)).toHaveAttribute("src", SRC);
        expect(screen.queryByRole("status")).toBeNull();
    });

    it.each([
        ["missing", messages.review.detail.pdf.missing],
        ["not_previewable", messages.review.detail.pdf.not_previewable],
    ] as const)("shows an empty state and no frame when it is %s", (availability, text) => {
        renderWithIntl(<PdfPanel src={SRC} availability={availability} />);
        expect(screen.getByRole("status")).toHaveTextContent(text);
        expect(screen.queryByTitle(messages.review.detail.pdf.title)).toBeNull();
    });
});
