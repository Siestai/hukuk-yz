import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { FILE_ID, NEXT_FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import type { UploadOutcome } from "@/lib/upload-file";
import { UploadPanel, type UploadTarget } from "./upload-panel";

const push = vi.hoisted(() => vi.fn());
const refresh = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
const uploadFile = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST }) }));
vi.mock("@/lib/upload-file", () => ({ uploadFile }));

const { upload } = messages.files;
const pdf = new File(["%PDF"], "genelge.pdf", { type: "application/pdf" });
const second = new File(["x"], "tebligler.pdf", { type: "application/pdf" });
const ok = (id: string): UploadOutcome => ({ ok: true, file: { id } as never });
const fail = (code: string, params: Record<string, unknown> = {}): UploadOutcome => ({
    ok: false,
    code,
    params,
});

function setup(target: UploadTarget = { kind: "new" }, isAdmin = false) {
    const view = renderWithIntl(<UploadPanel target={target} isAdmin={isAdmin} />);
    const input = view.container.querySelector<HTMLInputElement>("input[type=file]")!;
    return { input, user: userEvent.setup() };
}

const items = () => screen.getAllByRole("listitem");

beforeEach(() => {
    uploadFile.mockReset();
    push.mockClear();
    refresh.mockClear();
    POST.mockReset();
});

describe("UploadPanel", () => {
    it("offers a picker for several files of the allowed types", () => {
        const { input } = setup();
        expect(screen.getByRole("button", { name: upload.choose })).toBeInTheDocument();
        expect(input.multiple).toBe(true);
        expect(input.accept).toBe(".pdf,.doc,.docx,.udf,.png,.jpg,.jpeg,.xlsx,.xlsm,.txt");
    });

    it("gives every chosen file a form, also for files dropped on the zone", async () => {
        const { input, user } = setup();
        await user.upload(input, [pdf, second]);
        expect(items()).toHaveLength(2);
        const dropped = new File(["y"], "dropped.pdf", { type: "application/pdf" });
        const zone = screen.getByRole("group", { name: upload.dropLabel });
        const event = new Event("drop", { bubbles: true, cancelable: true });
        Object.defineProperty(event, "dataTransfer", { value: { files: [dropped] } });
        zone.dispatchEvent(event);
        expect(await screen.findByText("dropped.pdf")).toBeInTheDocument();
        expect(items()).toHaveLength(3);
    });

    it("does not upload before every file has a document type", async () => {
        const { input, user } = setup();
        await user.upload(input, [pdf, second]);
        await user.selectOptions(screen.getAllByLabelText(upload.docTypeRequired)[0]!, "genelge");
        await user.click(screen.getByRole("button", { name: upload.submit }));
        expect(uploadFile).not.toHaveBeenCalled();
        expect(screen.getAllByText(upload.typeMissing)).toHaveLength(1);
    });

    it("uploads the files one after another with their fields, and refreshes the list", async () => {
        uploadFile.mockResolvedValueOnce(ok(FILE_ID)).mockResolvedValueOnce(ok(NEXT_FILE_ID));
        const { input, user } = setup();
        await user.upload(input, [pdf, second]);
        const types = screen.getAllByLabelText(upload.docTypeRequired);
        await user.selectOptions(types[0]!, "genelge");
        await user.selectOptions(types[1]!, "teblig");
        await user.type(screen.getAllByLabelText(upload.officialRef)[0]!, "2020/39");
        await user.click(screen.getByRole("button", { name: upload.submit }));

        await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
        expect(uploadFile).toHaveBeenCalledTimes(2);
        expect(uploadFile.mock.calls[0]?.slice(0, 3)).toEqual([
            "/api/files",
            pdf,
            { doc_type: "genelge", official_ref: "2020/39" },
        ]);
        expect(uploadFile.mock.calls[1]?.[2]).toEqual({ doc_type: "teblig" });
        const links = screen.getAllByRole("link", { name: upload.openRecord });
        expect(links.map((l) => l.getAttribute("href"))).toEqual([
            `/dosyalar/${FILE_ID}`,
            `/dosyalar/${NEXT_FILE_ID}`,
        ]);
    });

    it("shows the progress of the file that is being sent", async () => {
        let report: (fraction: number) => void = () => {};
        uploadFile.mockImplementation(
            (_url: string, _file: File, _fields: unknown, onProgress: typeof report) => {
                report = onProgress;
                return new Promise(() => {});
            },
        );
        const { input, user } = setup();
        await user.upload(input, pdf);
        await user.selectOptions(screen.getByLabelText(upload.docTypeRequired), "karar");
        await user.click(screen.getByRole("button", { name: upload.submit }));
        report(0.4);
        const bar = await screen.findByRole("progressbar", {
            name: upload.progress.replace("{name}", "genelge.pdf"),
        });
        await waitFor(() => expect(bar).toHaveAttribute("value", "40"));
        expect(screen.getByRole("button", { name: upload.uploading })).toBeDisabled();
    });

    it("says a duplicate is already uploaded and links to the record", async () => {
        uploadFile.mockResolvedValue(fail("duplicate_file", { file_id: FILE_ID, archived: false }));
        const { input, user } = setup();
        await user.upload(input, pdf);
        await user.selectOptions(screen.getByLabelText(upload.docTypeRequired), "karar");
        await user.click(screen.getByRole("button", { name: upload.submit }));
        const alert = await screen.findByRole("alert");
        expect(within(alert).getByText(upload.duplicate)).toBeInTheDocument();
        expect(within(alert).getByRole("link", { name: upload.openExisting })).toHaveAttribute(
            "href",
            `/dosyalar/${FILE_ID}`,
        );
        expect(within(alert).queryByRole("button", { name: upload.unarchive })).toBeNull();
    });

    it("says an archived duplicate is in the archive; only an admin can take it out", async () => {
        uploadFile.mockResolvedValue(fail("duplicate_file", { file_id: FILE_ID, archived: true }));
        POST.mockResolvedValue({ data: { id: FILE_ID } });
        const reviewer = setup();
        await reviewer.user.upload(reviewer.input, pdf);
        await reviewer.user.selectOptions(screen.getByLabelText(upload.docTypeRequired), "karar");
        await reviewer.user.click(screen.getByRole("button", { name: upload.submit }));
        const alert = await screen.findByRole("alert");
        expect(within(alert).getByText(upload.duplicateArchived)).toBeInTheDocument();
        expect(within(alert).queryByRole("button", { name: upload.unarchive })).toBeNull();
    });

    it("lets an admin take an archived duplicate out of the archive", async () => {
        uploadFile.mockResolvedValue(fail("duplicate_file", { file_id: FILE_ID, archived: true }));
        POST.mockResolvedValue({ data: { id: FILE_ID } });
        const { input, user } = setup({ kind: "new" }, true);
        await user.upload(input, pdf);
        await user.selectOptions(screen.getByLabelText(upload.docTypeRequired), "karar");
        await user.click(screen.getByRole("button", { name: upload.submit }));
        await user.click(await screen.findByRole("button", { name: upload.unarchive }));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/unarchive", {
            params: { path: { file_id: FILE_ID } },
        });
        expect(await screen.findByText(upload.unarchived)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: upload.unarchive })).toBeNull();
        expect(screen.getByText(upload.duplicate)).toBeInTheDocument();
    });

    it.each([
        ["file_too_large", messages.errors.file_too_large],
        ["unsupported_file_type", messages.errors.unsupported_file_type],
        ["upstream_unavailable", messages.errors.upstream_unavailable],
    ])("explains %s in Turkish and lets the file be sent again", async (code, text) => {
        uploadFile.mockResolvedValueOnce(fail(code)).mockResolvedValueOnce(ok(FILE_ID));
        const { input, user } = setup();
        await user.upload(input, pdf);
        await user.selectOptions(screen.getByLabelText(upload.docTypeRequired), "karar");
        await user.click(screen.getByRole("button", { name: upload.submit }));
        expect(await screen.findByRole("alert")).toHaveTextContent(text);
        await user.click(screen.getByRole("button", { name: upload.submit }));
        expect(await screen.findByRole("link", { name: upload.openRecord })).toBeInTheDocument();
    });

    it("removes a file from the list", async () => {
        const { input, user } = setup();
        await user.upload(input, [pdf, second]);
        await user.click(
            screen.getByRole("button", { name: upload.remove.replace("{name}", "genelge.pdf") }),
        );
        expect(items()).toHaveLength(1);
        expect(screen.queryByText("genelge.pdf")).toBeNull();
    });

    describe("as a new version", () => {
        it("takes one file, needs no type, and opens the new record", async () => {
            uploadFile.mockResolvedValue(ok(NEXT_FILE_ID));
            const { input, user } = setup({ kind: "version", fileId: FILE_ID });
            expect(input.multiple).toBe(false);
            await user.upload(input, pdf);
            expect(
                within(screen.getByLabelText(upload.docType)).getByRole("option", {
                    name: upload.sameAsPrevious,
                }),
            ).toBeInTheDocument();
            await user.click(screen.getByRole("button", { name: upload.submit }));
            await waitFor(() => expect(push).toHaveBeenCalledWith(`/dosyalar/${NEXT_FILE_ID}`));
            expect(uploadFile.mock.calls[0]?.[0]).toBe(`/api/files/${FILE_ID}/versions`);
            expect(uploadFile.mock.calls[0]?.[2]).toEqual({});
        });
    });
});
