import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ActionBar } from "@/components/review-detail/action-bar";
import { ReviewProvider } from "@/components/review-detail/review-session";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { renderWithIntl } from "@/test/intl";
import { NEXT_STATUTE_ID, STATUTE_ID } from "@/test/statute-fixtures";

const push = vi.hoisted(() => vi.fn());
const refresh = vi.hoisted(() => vi.fn());
const GET = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ GET, POST }) }));

const queue: StatuteQueueParams = { kind: "statute", statute: "5510", band: "high", page: 1 };
const done = { data: { review_id: "r1", article_id: "a1", source_status: "approved" } };

function setup(canAct = true) {
    return renderWithIntl(
        <ReviewProvider extractionId={STATUTE_ID} queue={queue} pos={2} canAct={canAct}>
            <ActionBar editable={false} />
        </ReviewProvider>,
    );
}

/** The statute queue of the API: it answers list calls by offset and limit; an action takes the article out. */
function serveQueue(ids: string[]) {
    let queued = ids;
    GET.mockImplementation(
        async (_path: string, init: { params: { query: { offset: number; limit: number } } }) => {
            const { offset, limit } = init.params.query;
            return {
                data: {
                    total: queued.length,
                    items: queued
                        .slice(offset, offset + limit)
                        .map((id) => ({ extraction_id: id })),
                },
            };
        },
    );
    POST.mockImplementation(async () => {
        queued = queued.filter((id) => id !== STATUTE_ID);
        return done;
    });
}

beforeEach(() => {
    vi.clearAllMocks();
    serveQueue(["p0", "p1", STATUTE_ID, NEXT_STATUTE_ID]);
});

const approve = () => userEvent.click(screen.getByRole("button", { name: /^Onayla/ }));

describe("review actions of a statute article", () => {
    it("has approve and reject but no edit", () => {
        setup();
        expect(screen.getByRole("button", { name: /^Onayla A$/ })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^Reddet R$/ })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Düzelt/ })).not.toBeInTheDocument();
        fireEvent.keyDown(document.body, { key: "e" });
        expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    });

    it("renders no actions for an article that is not pending", () => {
        setup(false);
        expect(screen.queryByRole("button", { name: /^Onayla/ })).not.toBeInTheDocument();
    });

    it("approves with the statute endpoint and moves to the next waiting article of the same filters", async () => {
        setup();
        await approve();
        await waitFor(() => expect(push).toHaveBeenCalled());
        expect(POST).toHaveBeenCalledWith("/review/statutes/{extraction_id}", {
            params: { path: { extraction_id: STATUTE_ID } },
            body: { action: "approve" },
        });
        expect(GET.mock.calls[0]?.[0]).toBe("/review/statutes");
        expect(GET.mock.calls[0]?.[1]).toMatchObject({
            params: { query: { statute: "5510", band: "high", limit: 1, offset: 2 } },
        });
        expect(push).toHaveBeenCalledWith(
            `/mevzuat/${NEXT_STATUTE_ID}?kanun=5510&band=high&pos=2&flash=approved`,
        );
    });

    it("ends the queue on /mevzuat when nothing else waits", async () => {
        serveQueue([STATUTE_ID]);
        setup();
        await approve();
        await waitFor(() =>
            expect(push).toHaveBeenCalledWith(
                "/mevzuat?kanun=5510&band=high&flash=approved&done=1",
            ),
        );
    });

    it("needs a note to reject, and sends it trimmed", async () => {
        const user = userEvent.setup();
        setup();
        await user.click(screen.getByRole("button", { name: /^Reddet/ }));
        const dialog = screen.getByRole("dialog", { name: "Maddeyi reddet" });
        const submit = within(dialog).getByRole("button", { name: "Reddet" });
        expect(submit).toBeDisabled();
        await user.type(within(dialog).getByLabelText("Ret notu"), "  m. 18 gap yanlış  ");
        expect(submit).toBeEnabled();
        await user.click(submit);
        await waitFor(() => expect(push).toHaveBeenCalled());
        expect(POST).toHaveBeenCalledWith("/review/statutes/{extraction_id}", {
            params: { path: { extraction_id: STATUTE_ID } },
            body: { action: "reject", note: "m. 18 gap yanlış" },
        });
        expect(push.mock.calls[0]?.[0]).toContain("flash=rejected");
    });

    it("shows the conflict of a second reviewer by its error code and offers a refresh", async () => {
        POST.mockResolvedValue({ error: { error: { code: "review_conflict", params: {} } } });
        setup();
        await approve();
        const alert = await screen.findByRole("alert");
        expect(alert).toHaveTextContent("Bu kaydı az önce başka biri işledi");
        await userEvent.click(within(alert).getByRole("button", { name: "Sayfayı yenile" }));
        expect(refresh).toHaveBeenCalled();
        expect(push).not.toHaveBeenCalled();
    });

    it("words a refused timeline for an article, not for a decision", async () => {
        POST.mockResolvedValue({
            error: { error: { code: "validation_error", params: { fields: [] } } },
        });
        setup();
        await approve();
        expect(await screen.findByRole("alert")).toHaveTextContent("Madde çizelgesi yayınlanamadı");
    });

    it("returns to /mevzuat from a tab other than the queue", async () => {
        renderWithIntl(
            <ReviewProvider
                extractionId={STATUTE_ID}
                queue={{ ...queue, status: "approved" }}
                pos={2}
                canAct
            >
                <ActionBar editable={false} />
            </ReviewProvider>,
        );
        await approve();
        await waitFor(() =>
            expect(push).toHaveBeenCalledWith(
                "/mevzuat?durum=onaylanan&kanun=5510&band=high&flash=approved",
            ),
        );
        expect(GET).not.toHaveBeenCalled();
    });
});
