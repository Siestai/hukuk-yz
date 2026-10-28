import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import { UploadScan } from "./upload-scan";

const GET = vi.hoisted(() => vi.fn());
vi.mock("@hukuk/web-core/api/client", () => ({ createApiClient: () => ({ GET }) }));

const { upload } = messages.files;
const state = (scan_status: string, review_status = "pending") => ({
    data: { scan_status, review_status },
});

beforeEach(() => {
    vi.useFakeTimers();
    GET.mockReset();
});
afterEach(() => vi.useRealTimers());

describe("UploadScan", () => {
    it("says Taranıyor, then Onay bekliyor with the way to the approval screen", async () => {
        GET.mockResolvedValueOnce(state("running")).mockResolvedValueOnce(state("done"));
        renderWithIntl(<UploadScan fileId={FILE_ID} />);
        expect(screen.getByText(upload.scanning)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: upload.openRecord })).toHaveAttribute(
            "href",
            `/dosyalar/${FILE_ID}`,
        );
        await act(() => vi.advanceTimersByTimeAsync(5_000));
        expect(GET).toHaveBeenCalledWith("/files/{file_id}", {
            params: { path: { file_id: FILE_ID } },
        });
        expect(screen.getByText(upload.scanning)).toBeInTheDocument();
        await act(() => vi.advanceTimersByTimeAsync(5_000));
        expect(screen.getByText(messages.enums.reviewStatus.pending)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: upload.reviewNow })).toHaveAttribute(
            "href",
            `/dosyalar/${FILE_ID}`,
        );
        await act(() => vi.advanceTimersByTimeAsync(60_000));
        expect(GET).toHaveBeenCalledTimes(2);
    });

    it("shows the state of a scan that ends without a text and offers the record", async () => {
        GET.mockResolvedValue(state("needs_ocr"));
        renderWithIntl(<UploadScan fileId={FILE_ID} />);
        await act(() => vi.advanceTimersByTimeAsync(5_000));
        expect(screen.getByText(messages.enums.scanStatus.needs_ocr)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: upload.openRecord })).toBeInTheDocument();
    });

    it("keeps asking after a failed request, for 2 minutes at most", async () => {
        GET.mockRejectedValue(new TypeError("fetch failed"));
        renderWithIntl(<UploadScan fileId={FILE_ID} />);
        await act(() => vi.advanceTimersByTimeAsync(10 * 60_000));
        expect(GET).toHaveBeenCalledTimes(23);
    });

    it("stops saying Taranıyor after 2 minutes and points to the record", async () => {
        GET.mockResolvedValue(state("running"));
        renderWithIntl(<UploadScan fileId={FILE_ID} />);
        await act(() => vi.advanceTimersByTimeAsync(60_000));
        expect(screen.getByText(upload.scanning)).toBeInTheDocument();
        await act(() => vi.advanceTimersByTimeAsync(65_000));
        expect(screen.queryByText(upload.scanning)).toBeNull();
        expect(screen.getByText(upload.scanTimeout)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: upload.openRecord })).toHaveAttribute(
            "href",
            `/dosyalar/${FILE_ID}`,
        );
    });

    it("does not ask while the tab is hidden", async () => {
        const hidden = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
        renderWithIntl(<UploadScan fileId={FILE_ID} />);
        await act(() => vi.advanceTimersByTimeAsync(15_000));
        expect(GET).not.toHaveBeenCalled();
        hidden.mockRestore();
    });
});
