import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { components } from "@/lib/api/schema";
import { renderWithIntl } from "@/test/intl";
import { ActionBar } from "./action-bar";
import { ReviewProvider } from "./review-session";
import { ReviewStatusStrip } from "./review-status-strip";

const push = vi.hoisted(() => vi.fn());
const GET = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ GET, POST: vi.fn() }) }));

type Review = components["schemas"]["ReviewOut"];

const ID = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
const NEXT = "7a1d5c2e-1b34-4c8e-9f60-0d2b8e4a7c11";
const strip = messages.review.detail.statusStrip;
const review: Review = {
    id: "r1",
    reviewer_id: "u1",
    reviewer_name: "İbrahim",
    decision: "reject",
    edits: null,
    note: "Kopya kayıt, aynı karar başka sayıda var.",
    reviewed_at: "2026-10-04T09:30:00Z",
};

function setup(sourceStatus: string, reviews: Review[], queue = { status: "rejected" } as const) {
    return renderWithIntl(
        <ReviewProvider
            extractionId={ID}
            queue={{ ...queue, sort: "reviewed_desc", page: 1 }}
            pos={1}
            canAct={sourceStatus === "analyzed"}
        >
            <ReviewStatusStrip sourceStatus={sourceStatus} reviews={reviews} />
            <ActionBar />
        </ReviewProvider>,
    );
}

beforeEach(() => vi.clearAllMocks());

describe("ReviewStatusStrip", () => {
    it("shows the rejection with its date, reviewer and note, and no actions", () => {
        setup("rejected", [review]);
        const region = screen.getByRole("region", { name: strip.label });
        expect(region).toHaveTextContent(/Reddedildi · 04\.10\.2026.* · İbrahim/);
        expect(region).toHaveTextContent(`${strip.note}: ${review.note}`);
        expect(screen.queryByRole("region", { name: messages.review.actions.label })).toBeNull();
        expect(screen.queryByRole("button", { name: /Onayla/ })).toBeNull();
    });

    it("tells an approval with corrections from a plain one, without a note", () => {
        const approved: Review = { ...review, decision: "approve", note: "iyi" };
        const { unmount } = setup("approved", [approved]);
        expect(screen.getByRole("region", { name: strip.label })).toHaveTextContent(
            /^Onaylandı · /,
        );
        expect(screen.queryByText(new RegExp(strip.note))).toBeNull();
        unmount();
        setup("approved", [{ ...approved, decision: "edit", edits: { chamber: "22. HD" } }]);
        expect(screen.getByRole("region", { name: strip.label })).toHaveTextContent(
            /^Düzeltilerek onaylandı · /,
        );
    });

    it("names the last review when there are several, and an unknown reviewer", () => {
        const older: Review = { ...review, id: "r0", reviewer_name: "Baran", decision: "approve" };
        setup("rejected", [older, { ...review, reviewer_name: null }]);
        const region = screen.getByRole("region", { name: strip.label });
        expect(region).toHaveTextContent(messages.review.detail.unknownReviewer);
        expect(region).not.toHaveTextContent("Baran");
    });

    it("is not shown for a record still waiting", () => {
        setup("analyzed", []);
        expect(screen.queryByRole("region", { name: strip.label })).toBeNull();
    });

    it("lets J go to the next record of the tab's list from a reviewed record", async () => {
        GET.mockImplementation(async (_path: string, init: { params: { query: object } }) => {
            const query = init.params.query as { offset: number };
            const ids = ["p0", ID, NEXT];
            return {
                data: {
                    total: 3,
                    items: [{ extraction_id: ids[query.offset] }].filter((i) => i.extraction_id),
                },
            };
        });
        setup("rejected", [review]);
        fireEvent.keyDown(document.body, { key: "j" });
        await vi.waitFor(() => expect(push).toHaveBeenCalled());
        expect(push).toHaveBeenCalledWith(`/kararlar/${NEXT}?durum=reddedilen&pos=2`);
        expect(GET.mock.calls[0]![1]).toMatchObject({
            params: { query: { status: "rejected", sort: "reviewed_desc" } },
        });
    });

    it("says there is no next record at the end of the list", async () => {
        GET.mockImplementation(async (_path: string, init: { params: { query: object } }) => {
            const { offset } = init.params.query as { offset: number };
            return { data: { total: 2, items: offset === 1 ? [{ extraction_id: ID }] : [] } };
        });
        setup("rejected", [review]);
        fireEvent.keyDown(document.body, { key: "j" });
        expect(await screen.findByText(messages.review.actions.noNext)).toBeInTheDocument();
    });

    it("does not open the reject dialog by the R key on a reviewed record", () => {
        setup("rejected", [review]);
        fireEvent.keyDown(document.body, { key: "r" });
        expect(screen.queryByRole("dialog")).toBeNull();
    });
});
