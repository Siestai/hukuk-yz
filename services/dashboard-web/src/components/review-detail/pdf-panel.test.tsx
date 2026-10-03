import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { PdfPanel } from "./pdf-panel";

const SRC = "/api/review/decisions/d1/file";
const fetchMock = vi.fn();
vi.stubGlobal("fetch", fetchMock);
afterEach(() => fetchMock.mockReset());

const errorBody = (status: number, code: string) =>
    new Response(JSON.stringify({ error: { code, params: {} } }), { status });

describe("PdfPanel", () => {
    it("shows the PDF in a titled iframe once the file answers, without reading its body", async () => {
        const cancel = vi.fn();
        fetchMock.mockResolvedValue({ ok: true, body: { cancel } });
        renderWithIntl(<PdfPanel src={SRC} />);
        expect(screen.getByRole("status")).toHaveTextContent(messages.review.detail.pdf.checking);
        const frame = await screen.findByTitle(messages.review.detail.pdf.title);
        expect(frame).toHaveAttribute("src", SRC);
        expect(fetchMock).toHaveBeenCalledWith(
            SRC,
            expect.objectContaining({ signal: expect.anything() }),
        );
        expect(cancel).toHaveBeenCalled();
    });

    it.each([
        ["file_not_found", 404, messages.review.detail.pdf.file_not_found],
        ["file_not_previewable", 415, messages.review.detail.pdf.file_not_previewable],
    ])("shows an empty state for %s and no frame, no retry", async (code, status, text) => {
        fetchMock.mockResolvedValue(errorBody(status, code));
        renderWithIntl(<PdfPanel src={SRC} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(text);
        expect(screen.queryByTitle(messages.review.detail.pdf.title)).toBeNull();
        expect(screen.queryByRole("button")).toBeNull();
    });

    it("offers a retry for any other failure and loads the frame when it works", async () => {
        fetchMock.mockResolvedValueOnce(errorBody(502, "upstream_unavailable"));
        renderWithIntl(<PdfPanel src={SRC} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.review.detail.pdf.unavailable,
        );
        fetchMock.mockResolvedValueOnce({ ok: true, body: null });
        await userEvent.click(
            screen.getByRole("button", { name: messages.review.detail.pdf.retry }),
        );
        expect(await screen.findByTitle(messages.review.detail.pdf.title)).toBeInTheDocument();
        expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it("treats a network failure and a non-JSON error body as unavailable", async () => {
        fetchMock.mockRejectedValue(new TypeError("fetch failed"));
        renderWithIntl(<PdfPanel src={SRC} />);
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.review.detail.pdf.unavailable,
        );
    });

    it("aborts the probe when it unmounts and shows nothing afterwards", async () => {
        let signal: AbortSignal | undefined;
        fetchMock.mockImplementation((_url: string, init: RequestInit) => {
            signal = init.signal ?? undefined;
            return new Promise((_, reject) =>
                init.signal?.addEventListener("abort", () => reject(new Error("aborted"))),
            );
        });
        const { unmount } = renderWithIntl(<PdfPanel src={SRC} />);
        unmount();
        await waitFor(() => expect(signal?.aborted).toBe(true));
    });
});
