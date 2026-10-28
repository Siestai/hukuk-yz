import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import { FileText } from "./file-text";

const GET = vi.hoisted(() => vi.fn());
vi.mock("@hukuk/web-core/api/client", () => ({ createApiClient: () => ({ GET }) }));

const { text } = messages.files.detail;

beforeEach(() => GET.mockReset());

describe("FileText", () => {
    it("fetches the text when it is opened and hides it again", async () => {
        GET.mockResolvedValue({ data: "Madde 1\n\nİş sözleşmesi" });
        renderWithIntl(<FileText fileId={FILE_ID} />);
        expect(GET).not.toHaveBeenCalled();
        await userEvent.click(screen.getByRole("button", { name: text.show }));
        const article = await screen.findByRole("article", { name: text.label });
        expect(article).toHaveTextContent("İş sözleşmesi");
        expect(GET).toHaveBeenCalledWith("/files/{file_id}/text", {
            params: { path: { file_id: FILE_ID } },
            parseAs: "text",
        });
        await userEvent.click(screen.getByRole("button", { name: text.hide }));
        expect(screen.queryByRole("article")).toBeNull();
    });

    it("says so when the file has no text", async () => {
        GET.mockResolvedValue({ data: "  " });
        renderWithIntl(<FileText fileId={FILE_ID} />);
        await userEvent.click(screen.getByRole("button", { name: text.show }));
        expect(await screen.findByText(text.empty)).toBeInTheDocument();
    });

    it("says so when the text cannot be fetched, and tries again on the next click", async () => {
        GET.mockResolvedValueOnce({ error: { error: { code: "file_not_found", params: {} } } });
        GET.mockResolvedValueOnce({ data: "metin" });
        renderWithIntl(<FileText fileId={FILE_ID} />);
        await userEvent.click(screen.getByRole("button", { name: text.show }));
        expect(await screen.findByRole("alert")).toHaveTextContent(text.failed);
        await userEvent.click(screen.getByRole("button", { name: text.show }));
        expect(await screen.findByRole("article")).toHaveTextContent("metin");
    });
});
