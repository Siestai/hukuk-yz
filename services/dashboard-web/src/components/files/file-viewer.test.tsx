import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import { FileViewer } from "./file-viewer";

const viewer = messages.files.detail.viewer;
const SRC = `/api/files/${FILE_ID}/content`;

vi.mock("@/components/pdf-viewer/pdf-viewer", () => ({
    PdfViewer: ({ src }: { src: string }) => <div data-testid="pdf-viewer" data-src={src} />,
}));

describe("FileViewer", () => {
    it("is only a link to the file for a type that is not a PDF", () => {
        renderWithIntl(<FileViewer fileId={FILE_ID} pdf={false} />);
        const link = screen.getByRole("link", { name: viewer.open });
        expect(link).toHaveAttribute("href", SRC);
        expect(link).toHaveAttribute("target", "_blank");
        expect(screen.queryByRole("button")).toBeNull();
        expect(screen.queryByTitle(viewer.title)).toBeNull();
    });

    it("keeps the lazy frame and the link for a wide screen, hidden on a phone", () => {
        renderWithIntl(<FileViewer fileId={FILE_ID} pdf />);
        const frame = screen.getByTitle(viewer.title);
        expect(frame).toHaveAttribute("src", SRC);
        expect(frame).toHaveAttribute("loading", "lazy");
        expect(frame).toHaveClass("hidden", "md:block");
        expect(screen.getByRole("link", { name: viewer.open })).toHaveClass("hidden");
        expect(screen.getByRole("button", { name: viewer.open })).toHaveClass("md:hidden");
    });

    it("opens the PDF.js viewer in a window from the phone button and returns the focus", async () => {
        renderWithIntl(<FileViewer fileId={FILE_ID} pdf />);
        expect(screen.queryByRole("dialog")).toBeNull();
        const opener = screen.getByRole("button", { name: viewer.open });
        await userEvent.click(opener);
        const dialog = screen.getByRole("dialog", { name: viewer.title });
        expect(within(dialog).getByTestId("pdf-viewer")).toHaveAttribute("data-src", SRC);
        await userEvent.click(within(dialog).getByRole("button", { name: viewer.close }));
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(opener).toHaveFocus();
    });
});
