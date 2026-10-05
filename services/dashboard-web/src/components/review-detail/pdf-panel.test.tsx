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

    it("offers the file in a new tab on a phone, where the frame is hidden and not loaded", () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        const link = screen.getByRole("link", { name: messages.review.detail.pdf.open });
        expect(link).toHaveAttribute("href", SRC);
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener");
        expect(link.closest("a")).toHaveClass("md:hidden");
        const frame = screen.getByTitle(messages.review.detail.pdf.title);
        expect(frame).toHaveClass("hidden", "md:block");
        expect(frame).toHaveAttribute("loading", "lazy");
    });

    it("has no link when there is no file", () => {
        renderWithIntl(<PdfPanel src={SRC} availability="missing" />);
        expect(screen.queryByRole("link")).toBeNull();
    });
});
