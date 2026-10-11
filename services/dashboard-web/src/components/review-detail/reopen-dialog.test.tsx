import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { components } from "@/lib/api/schema";
import { renderWithIntl } from "@/test/intl";
import { ReviewProvider } from "./review-session";
import { ReviewStatusStrip } from "./review-status-strip";

const refresh = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ GET: vi.fn(), POST }) }));

type Review = components["schemas"]["ReviewOut"];

const ID = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
const reopen = messages.review.reopen;
const review: Review = {
    id: "r1",
    reviewer_id: "u1",
    reviewer_name: "İbrahim",
    decision: "approve",
    edits: null,
    note: null,
    reviewed_at: "2026-10-04T09:30:00Z",
};

function setup(sourceStatus: string, decision: Review["decision"] = "approve") {
    return renderWithIntl(
        <ReviewProvider
            extractionId={ID}
            queue={{ status: "approved", sort: "reviewed_desc", page: 1 }}
            pos={1}
            canAct={sourceStatus === "analyzed"}
        >
            <ReviewStatusStrip sourceStatus={sourceStatus} reviews={[{ ...review, decision }]} />
        </ReviewProvider>,
    );
}

beforeEach(() => {
    vi.clearAllMocks();
    POST.mockResolvedValue({ data: { review_id: "r2", decision_id: null } });
});

describe("reopening a reviewed decision", () => {
    it("offers 'Onaydan çıkar' on an approved record and 'Reddi geri al' on a rejected one", () => {
        const { unmount } = setup("approved");
        expect(screen.getByRole("button", { name: reopen.fromApproved })).toBeInTheDocument();
        unmount();
        setup("rejected", "reject");
        expect(screen.getByRole("button", { name: reopen.fromRejected })).toBeInTheDocument();
    });

    it("has no button for a record that is waiting", () => {
        setup("analyzed");
        expect(screen.queryByRole("button")).toBeNull();
    });

    it("explains what happens, posts the note and refreshes the page", async () => {
        setup("approved");
        await userEvent.click(screen.getByRole("button", { name: reopen.fromApproved }));
        const dialog = screen.getByRole("dialog", { name: reopen.title });
        expect(dialog).toHaveTextContent(reopen.intro);
        await userEvent.type(screen.getByLabelText(reopen.note), " yanlış onay ");
        await userEvent.click(screen.getByRole("button", { name: reopen.submit }));
        await vi.waitFor(() => expect(refresh).toHaveBeenCalled());
        expect(POST).toHaveBeenCalledWith("/review/decisions/{extraction_id}", {
            params: { path: { extraction_id: ID } },
            body: { action: "reopen", note: "yanlış onay" },
        });
        expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("works without a note and closes on Escape, returning the focus to the button", async () => {
        setup("approved");
        const button = screen.getByRole("button", { name: reopen.fromApproved });
        await userEvent.click(button);
        fireEvent(screen.getByRole("dialog"), new Event("cancel", { cancelable: true }));
        await vi.waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
        expect(button).toHaveFocus();
        expect(POST).not.toHaveBeenCalled();
        await userEvent.click(button);
        await userEvent.click(screen.getByRole("button", { name: reopen.submit }));
        await vi.waitFor(() => expect(POST).toHaveBeenCalled());
        expect((POST.mock.calls[0] as [string, { body: unknown }])[1].body).toEqual({
            action: "reopen",
            note: undefined,
        });
    });

    it("says someone else changed the record and refreshes, on a 409", async () => {
        POST.mockResolvedValue({ error: { error: { code: "review_conflict", params: {} } } });
        setup("approved");
        await userEvent.click(screen.getByRole("button", { name: reopen.fromApproved }));
        await userEvent.click(screen.getByRole("button", { name: reopen.submit }));
        expect(await screen.findByRole("alert")).toHaveTextContent(reopen.conflict);
        expect(refresh).toHaveBeenCalled();
    });

    it("keeps the dialog open with the note and shows the error on a server failure", async () => {
        POST.mockResolvedValue({ error: { error: { code: "internal_error", params: {} } } });
        setup("approved");
        await userEvent.click(screen.getByRole("button", { name: reopen.fromApproved }));
        await userEvent.type(screen.getByLabelText(reopen.note), "yanlış onay");
        await userEvent.click(screen.getByRole("button", { name: reopen.submit }));
        const dialog = screen.getByRole("dialog", { name: reopen.title });
        expect(await within(dialog).findByRole("alert")).toHaveTextContent(messages.errors.generic);
        expect(screen.getAllByRole("alert")).toHaveLength(1);
        expect(screen.getByLabelText(reopen.note)).toHaveValue("yanlış onay");
        expect(refresh).not.toHaveBeenCalled();
    });
});
