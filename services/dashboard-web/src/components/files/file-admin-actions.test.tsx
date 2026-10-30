import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import { FileAdminActions } from "./file-admin-actions";

const refresh = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@hukuk/web-core/api/client", () => ({ createApiClient: () => ({ POST }) }));

const { actions } = messages.files.detail;
const path = {
    params: { path: { file_id: FILE_ID } },
    headers: { "Content-Type": "application/json" },
};

beforeEach(() => {
    POST.mockReset();
    refresh.mockClear();
});

describe("FileAdminActions", () => {
    it("archives a file and refreshes the page", async () => {
        POST.mockResolvedValue({ data: {} });
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived={false} approved={false} />);
        await userEvent.click(screen.getByRole("button", { name: actions.archive }));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/archive", path);
        expect(refresh).toHaveBeenCalled();
    });

    it("takes an archived file out of the archive", async () => {
        POST.mockResolvedValue({ data: {} });
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived approved={false} />);
        expect(screen.queryByRole("button", { name: actions.archive })).toBeNull();
        await userEvent.click(screen.getByRole("button", { name: actions.unarchive }));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/unarchive", path);
    });

    it("queues a rescan", async () => {
        POST.mockResolvedValue({ data: {} });
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived={false} approved={false} />);
        await userEvent.click(screen.getByRole("button", { name: actions.rescan }));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/rescan", path);
    });

    it("takes the approval back of an approved file only", async () => {
        POST.mockResolvedValue({ data: {} });
        const { unmount } = renderWithIntl(
            <FileAdminActions fileId={FILE_ID} archived={false} approved={false} />,
        );
        expect(screen.queryByRole("button", { name: actions.unapprove })).toBeNull();
        unmount();
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived={false} approved />);
        await userEvent.click(screen.getByRole("button", { name: actions.unapprove }));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/unapprove", path);
        expect(refresh).toHaveBeenCalled();
    });

    it("explains that a file with a newer version keeps its approval", async () => {
        POST.mockResolvedValue({
            error: { error: { code: "file_has_newer_version", params: {} } },
        });
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived={false} approved />);
        await userEvent.click(screen.getByRole("button", { name: actions.unapprove }));
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.errors.file_has_newer_version,
        );
        expect(refresh).not.toHaveBeenCalled();
    });

    it("says a scan is in progress when the API answers 409 scan_in_progress", async () => {
        POST.mockResolvedValue({ error: { error: { code: "scan_in_progress", params: {} } } });
        renderWithIntl(<FileAdminActions fileId={FILE_ID} archived={false} approved={false} />);
        await userEvent.click(screen.getByRole("button", { name: actions.rescan }));
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.errors.scan_in_progress,
        );
        expect(refresh).not.toHaveBeenCalled();
    });
});
