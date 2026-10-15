import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { PdfViewer, ZOOM_STEPS } from "./pdf-viewer";

const SRC = "/api/files/f1/content";
const pdf = messages.pdfViewer;

const pdfjs = vi.hoisted(() => {
    class RenderingCancelledException extends Error {}
    return {
        RenderingCancelledException,
        getDocument: vi.fn(),
        TextLayer: vi.fn(),
    };
});
vi.mock("./load-pdfjs", () => ({ loadPdfjs: async () => pdfjs }));

/** A document of `pages` pages, each 600 x 800 points; every page's `render` resolves at once. */
function document(pages: number) {
    const render = vi.fn(() => ({ promise: Promise.resolve(), cancel: vi.fn() }));
    const page = {
        getViewport: ({ scale }: { scale: number }) => ({
            width: 600 * scale,
            height: 800 * scale,
        }),
        render,
        streamTextContent: vi.fn(),
    };
    const destroy = vi.fn(async () => {});
    pdfjs.getDocument.mockReturnValue({
        promise: Promise.resolve({ numPages: pages, getPage: async () => page }),
        destroy,
    });
    return { destroy, render };
}

beforeEach(() => {
    pdfjs.getDocument.mockReset();
    pdfjs.TextLayer.mockReset();
    pdfjs.TextLayer.mockImplementation(function () {
        return { render: async () => {}, cancel: vi.fn() };
    });
    // jsdom draws nothing and has no observers.
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ({})) as never;
    vi.stubGlobal(
        "ResizeObserver",
        class {
            constructor(private readonly callback: () => void) {}
            observe() {
                this.callback();
            }
            disconnect() {}
        },
    );
    vi.stubGlobal(
        "IntersectionObserver",
        class {
            constructor(
                private readonly callback: (entries: { isIntersecting: boolean }[]) => void,
            ) {}
            observe() {
                this.callback([{ isIntersecting: true }]);
            }
            disconnect() {}
        },
    );
});

describe("PdfViewer", () => {
    it("loads the file by its URL and shows a placeholder until the document is read", async () => {
        document(2);
        renderWithIntl(<PdfViewer src={SRC} />);
        expect(screen.getByRole("status", { name: pdf.loading })).toBeInTheDocument();
        await waitFor(() => expect(screen.queryByRole("status", { name: pdf.loading })).toBeNull());
        expect(pdfjs.getDocument).toHaveBeenCalledWith({ url: SRC });
    });

    it("stacks one page per PDF page in a labelled scrolling region and draws each", async () => {
        const { render } = document(3);
        const { container } = renderWithIntl(<PdfViewer src={SRC} />);
        const region = await screen.findByRole("region", { name: pdf.pages });
        await waitFor(() => expect(render).toHaveBeenCalledTimes(3));
        expect(region.querySelectorAll("canvas")).toHaveLength(3);
        expect(container.querySelectorAll("[data-page]")).toHaveLength(3);
        expect(pdfjs.TextLayer).toHaveBeenCalledTimes(3);
    });

    it("keeps the new-tab link as the way out", async () => {
        document(1);
        renderWithIntl(<PdfViewer src={SRC} />);
        const link = await screen.findByRole("link", { name: pdf.newTab });
        expect(link).toHaveAttribute("href", SRC);
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener");
    });

    it("zooms in and out in steps and stops at both ends", async () => {
        document(1);
        renderWithIntl(<PdfViewer src={SRC} />);
        const zoomIn = await screen.findByRole("button", { name: pdf.zoomIn });
        const zoomOut = screen.getByRole("button", { name: pdf.zoomOut });
        const level = screen.getByLabelText(pdf.zoom);
        expect(level).toHaveTextContent("100%");
        expect(zoomOut).toBeDisabled();
        await userEvent.click(zoomIn);
        expect(level).toHaveTextContent("125%");
        for (let step = 2; step < ZOOM_STEPS.length; step++) await userEvent.click(zoomIn);
        expect(level).toHaveTextContent("300%");
        expect(zoomIn).toBeDisabled();
        await userEvent.click(zoomOut);
        expect(level).toHaveTextContent("200%");
    });

    it("says so, with the new-tab link, when the document cannot be read", async () => {
        pdfjs.getDocument.mockReturnValue({
            promise: Promise.reject(new Error("bad")),
            destroy: vi.fn(async () => {}),
        });
        renderWithIntl(<PdfViewer src={SRC} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(pdf.failed);
        expect(screen.getByRole("link", { name: pdf.newTab })).toHaveAttribute("href", SRC);
        expect(screen.queryByRole("region")).toBeNull();
    });

    it("says so when a page cannot be drawn", async () => {
        const { render } = document(1);
        render.mockImplementation(() => ({
            promise: Promise.reject(new Error("bad")),
            cancel: vi.fn(),
        }));
        renderWithIntl(<PdfViewer src={SRC} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(pdf.failed);
    });

    it("gives the document back to PDF.js when it closes", async () => {
        const { destroy } = document(1);
        const { unmount } = renderWithIntl(<PdfViewer src={SRC} />);
        await screen.findByRole("region", { name: pdf.pages });
        unmount();
        expect(destroy).toHaveBeenCalled();
    });
});
