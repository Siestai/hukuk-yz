import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { PdfPanel } from "./pdf-panel";

const SRC = "/api/review/decisions/d1/file";
const pdf = messages.review.detail.pdf;

vi.mock("@/components/pdf-viewer/pdf-viewer", () => ({
    PdfViewer: ({ src }: { src: string }) => <div data-testid="pdf-viewer" data-src={src} />,
}));

describe("PdfPanel", () => {
    it("renders the titled iframe straight away when the PDF is available", () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        expect(screen.getByTitle(pdf.title)).toHaveAttribute("src", SRC);
        expect(screen.queryByRole("status")).toBeNull();
    });

    it.each([
        ["missing", pdf.missing],
        ["not_previewable", pdf.not_previewable],
    ] as const)(
        "shows an empty state and no frame or button when it is %s",
        (availability, text) => {
            renderWithIntl(<PdfPanel src={SRC} availability={availability} />);
            expect(screen.getByRole("status")).toHaveTextContent(text);
            expect(screen.queryByTitle(pdf.title)).toBeNull();
            expect(screen.queryByRole("button")).toBeNull();
        },
    );

    it("keeps the inline frame hidden and not loaded on a phone, with a button instead", () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        expect(screen.getByRole("button", { name: pdf.open })).toHaveClass("md:hidden");
        const frame = screen.getByTitle(pdf.title);
        expect(frame).toHaveClass("hidden", "md:block");
        expect(frame).toHaveAttribute("loading", "lazy");
        expect(screen.queryByRole("link")).toBeNull();
    });

    it("opens the file in a window over the page, with a new-tab link as the fallback", async () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        expect(screen.queryByRole("dialog")).toBeNull();
        await userEvent.click(screen.getByRole("button", { name: pdf.open }));
        const dialog = screen.getByRole("dialog", { name: pdf.title });
        expect(within(dialog).getByTitle(pdf.title)).toHaveAttribute("src", SRC);
        const link = within(dialog).getByRole("link", { name: pdf.newTab });
        expect(link).toHaveAttribute("href", SRC);
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener");
    });

    it("opens the same window from the wide-screen button", async () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        await userEvent.click(screen.getByRole("button", { name: pdf.openLarge }));
        expect(screen.getByRole("dialog", { name: pdf.title })).toBeInTheDocument();
    });

    it("closes with the close button and gives the focus back to the button that opened it", async () => {
        renderWithIntl(<PdfPanel src={SRC} availability="available" />);
        const opener = screen.getByRole("button", { name: pdf.openLarge });
        await userEvent.click(opener);
        await userEvent.click(screen.getByRole("button", { name: pdf.close }));
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(opener).toHaveFocus();
    });

    describe("on a phone", () => {
        const original = window.matchMedia;
        afterEach(() => {
            window.matchMedia = original;
        });

        it("draws the pages with PDF.js in the window instead of a frame", async () => {
            window.matchMedia = ((query: string) => ({
                matches: true,
                media: query,
                addEventListener: () => {},
                removeEventListener: () => {},
            })) as unknown as typeof window.matchMedia;
            renderWithIntl(<PdfPanel src={SRC} availability="available" />);
            await userEvent.click(screen.getByRole("button", { name: pdf.open }));
            const dialog = screen.getByRole("dialog", { name: pdf.title });
            expect(within(dialog).getByTestId("pdf-viewer")).toHaveAttribute("data-src", SRC);
            expect(within(dialog).queryByTitle(pdf.title)).toBeNull();
        });
    });
});
