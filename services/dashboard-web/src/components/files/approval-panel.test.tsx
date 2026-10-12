import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { FILE_ID, NEXT_FILE_ID, pendingFile } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import type { FileOut } from "@/lib/files";
import { ApprovalPanel } from "./approval-panel";

const push = vi.hoisted(() => vi.fn());
const refresh = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
const DELETE = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST, DELETE }) }));

const approve = messages.files.detail.approve;
const PREVIOUS_ID = "9b2e7d41-5c68-4f0a-8e13-6a7c1d2f3b44";
const names = { [PREVIOUS_ID]: "genelge-2024-4.pdf", [NEXT_FILE_ID]: "kopya.pdf" };

function setup(change: Partial<FileOut> = {}, canDelete = true) {
    return renderWithIntl(
        <ApprovalPanel file={{ ...pendingFile, ...change }} names={names} canDelete={canDelete} />,
    );
}

const field = (name: string) => screen.getByLabelText(name, { exact: true });
const error = (code: string) => ({ error: { error: { code, params: {} } } });
const withPrevious = {
    matches: {
        previous_version: { file_id: PREVIOUS_ID, reason: "same_ref" },
        similar: [{ file_id: NEXT_FILE_ID, score: 0.83, reason: "same_name" }],
    },
};

beforeEach(() => {
    vi.clearAllMocks();
    POST.mockResolvedValue({ data: {} });
    DELETE.mockResolvedValue({ response: new Response(null, { status: 204 }) });
});

describe("ApprovalPanel fields", () => {
    it("fills every field with the suggested value, its source and the quote with its page", () => {
        setup();
        expect(field(approve.docType)).toHaveValue("genelge");
        expect(field(approve.docDate)).toHaveValue("2024-03-01");
        expect(field(approve.officialRef)).toHaveValue("2024/5");
        expect(screen.getAllByText(messages.enums.suggestionSource.rule)).toHaveLength(2);
        expect(screen.getByText(/1\. sayfa: 'GENELGE 2024\/5'/)).toBeInTheDocument();
        expect(screen.getByText(/1\. sayfa: 'Sayı: E-12345 01.03.2024'/)).toBeInTheDocument();
    });

    it("warns about an LLM suggestion without evidence", () => {
        setup();
        expect(screen.getByText(messages.enums.suggestionSource.llm)).toBeInTheDocument();
        expect(screen.getByRole("note")).toHaveTextContent(approve.unsupported);
    });

    it("calls a value the user changed theirs and drops the quote and the warning", async () => {
        const user = userEvent.setup();
        setup();
        await user.clear(field(approve.officialRef));
        await user.type(field(approve.officialRef), "2024/6");
        expect(screen.queryByRole("note")).toBeNull();
        await user.selectOptions(field(approve.docType), "teblig");
        expect(screen.getAllByText(messages.enums.suggestionSource.user)).toHaveLength(2);
        expect(screen.queryByText(/GENELGE 2024\/5/)).toBeNull();
    });

    it("shows what the text said beside a value the user typed at the upload", () => {
        setup({
            suggestions: {
                doc_type: {
                    value: "kanun",
                    source: "user",
                    evidence: null,
                    detected: { value: "karar", source: "rule", evidence: null },
                },
            },
        });
        expect(field(approve.docType)).toHaveValue("kanun");
        expect(screen.getByText(messages.enums.suggestionSource.user)).toBeInTheDocument();
        expect(screen.getByText(approve.detected.replace("{value}", "Karar"))).toBeInTheDocument();
    });

    it("starts from the record's own values where nothing was suggested", () => {
        setup({ suggestions: null, doc_type: "kanun", note: "Drive'dan" });
        expect(field(approve.docType)).toHaveValue("kanun");
        expect(field(approve.note)).toHaveValue("Drive'dan");
        expect(screen.getByText(approve.noSuggestions)).toBeInTheDocument();
    });

    it("waits for the scan instead of showing an empty form", () => {
        setup({ scan_status: "running", suggestions: null });
        expect(screen.getByText(approve.scanning)).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: approve.approve })).toBeNull();
    });
});

describe("ApprovalPanel approval", () => {
    it("keeps Onayla off until a document type is chosen", async () => {
        const user = userEvent.setup();
        setup({ suggestions: null });
        const button = screen.getByRole("button", { name: approve.approve });
        expect(button).toBeDisabled();
        await user.selectOptions(field(approve.docType), "karar");
        expect(button).toBeEnabled();
    });

    it("sends the corrected fields, blank ones as empty, and refreshes the page", async () => {
        const user = userEvent.setup();
        setup();
        await user.clear(field(approve.officialRef));
        await user.type(field(approve.titleField), "Genelge 2024/5");
        await user.click(screen.getByRole("button", { name: approve.approve }));
        await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
        expect(POST).toHaveBeenCalledWith("/files/{file_id}/approve", {
            params: { path: { file_id: FILE_ID } },
            body: {
                doc_type: "genelge",
                doc_date: "2024-03-01",
                official_ref: null,
                title: "Genelge 2024/5",
                origin_url: null,
                note: null,
            },
        });
    });

    it.each([
        ["file_not_pending", messages.errors.file_not_pending, true],
        ["file_version_conflict", messages.errors.file_version_conflict, false],
        ["forbidden", messages.errors.forbidden, false],
        ["validation_error", messages.errors.validation_error, false],
        ["upstream_unavailable", messages.errors.upstream_unavailable, false],
    ])("explains %s in Turkish", async (code, text, refreshes) => {
        POST.mockResolvedValue(error(code));
        setup();
        await userEvent.click(screen.getByRole("button", { name: approve.approve }));
        expect(await screen.findByRole("alert")).toHaveTextContent(text);
        expect(refresh).toHaveBeenCalledTimes(refreshes ? 1 : 0);
    });
});

describe("ApprovalPanel matches", () => {
    it("offers the previous version with a choice that starts as a document of its own", async () => {
        const user = userEvent.setup();
        setup(withPrevious);
        const box = screen.getByRole("group", {
            name: approve.matches.previous
                .replace("{name}", "genelge-2024-4.pdf")
                .replace("{reason}", messages.enums.matchReason.same_ref),
        });
        expect(within(box).getByLabelText(approve.matches.separate)).toBeChecked();
        await user.click(screen.getByRole("button", { name: approve.approve }));
        await waitFor(() => expect(POST).toHaveBeenCalled());
        expect(POST.mock.calls[0]?.[1].body).toMatchObject({ supersedes_id: null });
    });

    it("links the file as the next version when that is chosen", async () => {
        const user = userEvent.setup();
        setup(withPrevious);
        await user.click(screen.getByLabelText(approve.matches.link));
        await user.click(screen.getByRole("button", { name: approve.approve }));
        await waitFor(() => expect(POST).toHaveBeenCalled());
        expect(POST.mock.calls[0]?.[1].body).toMatchObject({ supersedes_id: PREVIOUS_ID });
    });

    it("lists similar files as links that open in a new tab", () => {
        setup(withPrevious);
        expect(screen.getByText(approve.matches.similar)).toBeInTheDocument();
        const link = screen.getByRole("link", { name: /kopya\.pdf \(benzerlik %83\)/ });
        expect(link).toHaveAttribute("href", `/dosyalar/${NEXT_FILE_ID}`);
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
    });

    it("leaves the version link out of the request when there is no previous version", async () => {
        setup({ matches: { previous_version: null, similar: [] } });
        expect(screen.queryByRole("group")).toBeNull();
        await userEvent.click(screen.getByRole("button", { name: approve.approve }));
        await waitFor(() => expect(POST).toHaveBeenCalled());
        expect(POST.mock.calls[0]?.[1].body).not.toHaveProperty("supersedes_id");
    });
});

describe("ApprovalPanel delete", () => {
    it("asks before deleting, then deletes and goes back to the list", async () => {
        const user = userEvent.setup();
        setup({ original_name: "yanlis.pdf" });
        await user.click(screen.getByRole("button", { name: approve.delete }));
        const dialog = screen.getByRole("dialog", { name: approve.deleteDialog.title });
        expect(DELETE).not.toHaveBeenCalled();
        expect(dialog).toHaveTextContent("“yanlis.pdf” silinecek");
        await user.click(
            within(dialog).getByRole("button", { name: approve.deleteDialog.confirm }),
        );
        await waitFor(() => expect(push).toHaveBeenCalledWith("/dosyalar"));
        expect(DELETE).toHaveBeenCalledWith("/files/{file_id}", {
            params: { path: { file_id: FILE_ID } },
            headers: { "Content-Type": "application/json" },
        });
    });

    it("does nothing when the question is cancelled", async () => {
        const user = userEvent.setup();
        setup();
        await user.click(screen.getByRole("button", { name: approve.delete }));
        await user.click(screen.getByRole("button", { name: approve.deleteDialog.cancel }));
        expect(DELETE).not.toHaveBeenCalled();
        expect(screen.queryByRole("dialog")).toBeNull();
    });

    it.each([
        ["scan_in_progress", messages.errors.scan_in_progress],
        ["file_approved", messages.errors.file_approved],
        ["file_has_newer_version", messages.errors.file_has_newer_version],
        ["file_processed", messages.errors.file_processed],
        ["forbidden", messages.errors.forbidden],
    ])("explains %s in the dialog and stays on the page", async (code, text) => {
        DELETE.mockResolvedValue({ response: new Response(null, { status: 409 }), ...error(code) });
        const user = userEvent.setup();
        setup();
        await user.click(screen.getByRole("button", { name: approve.delete }));
        const dialog = within(screen.getByRole("dialog"));
        await user.click(dialog.getByRole("button", { name: approve.deleteDialog.confirm }));
        expect(await dialog.findByRole("alert")).toHaveTextContent(text);
        expect(push).not.toHaveBeenCalled();
        expect(dialog.getByRole("button", { name: approve.deleteDialog.confirm })).toBeEnabled();
    });

    it("has no Sil button for someone who may not delete the file", () => {
        setup({}, false);
        expect(screen.queryByRole("button", { name: approve.delete })).toBeNull();
    });
});
