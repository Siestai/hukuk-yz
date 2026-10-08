import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { QueueParams } from "@/lib/queue-params";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { renderWithIntl } from "@/test/intl";
import { BulkApproveDialog } from "./bulk-approve-dialog";
import type { BulkSample } from "./bulk-confirm-step";

const refresh = vi.hoisted(() => vi.fn());
const POST = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST }) }));

const { bulk } = messages.review;
const ID = (n: number) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const SHA = (n: number) => String(n).repeat(64);
const params = { band: "high", court: "bam", sort: "score_desc", page: 2 } as const;
const sample: BulkSample[] = [1, 2, 3, 4, 5].map((n) => ({
    id: ID(n),
    title: `KARAR ${n}`,
    esasNo: `2020/${n}`,
    kararNo: `2021/${n}`,
}));

const done = (over: Record<string, unknown>) => ({
    data: { published: 0, conflicts: [], failed: [], remaining: 0, next_cursor: null, ...over },
});
const refused = (code: string, params: Record<string, unknown> = {}) => ({
    error: { error: { code, params } },
});

const element = (total: number, onClose: () => void, p: QueueParams = params) => (
    <BulkApproveDialog
        onClose={onClose}
        returnFocusTo={{ current: null }}
        params={p}
        total={total}
        sample={sample}
    />
);

function setup(total = 250, onClose = vi.fn()) {
    const view = renderWithIntl(element(total, onClose));
    return { user: userEvent.setup(), onClose, view };
}

const dialog = () => screen.getByRole("dialog");
const checkbox = () => screen.getByRole("checkbox");
const start = () => screen.getByRole("button", { name: bulk.start });
const escape = () => fireEvent(dialog(), new Event("cancel", { cancelable: true }));

/** A call the test answers by hand, so it can look at the dialog while the call is in flight. */
function hold() {
    let release: (value: unknown) => void = () => {};
    POST.mockImplementationOnce(() => new Promise((resolve) => (release = resolve)));
    return (value: unknown) => act(async () => release(value));
}

beforeEach(() => {
    vi.clearAllMocks();
});

describe("BulkApproveDialog confirmation", () => {
    it("shows the count of the list, the active filters and the first five records", () => {
        setup(250);
        expect(within(dialog()).getByText("250 karar")).toBeInTheDocument();
        expect(within(dialog()).getByText("Güven: Yüksek")).toBeInTheDocument();
        expect(within(dialog()).getByText("Mahkeme: BAM")).toBeInTheDocument();
        for (const item of sample) {
            expect(within(dialog()).getByText(item.title)).toBeInTheDocument();
        }
        expect(within(dialog()).getByText("E. 2020/1 · K. 2021/1")).toBeInTheDocument();
    });

    it("keeps start disabled until the reviewer takes the exact count on as their own step", async () => {
        const { user } = setup(250);
        expect(start()).toBeDisabled();
        expect(screen.getByLabelText("Bu 250 kaydı kendi adımla onaylıyorum")).toBe(checkbox());
        await user.click(checkbox());
        expect(start()).toBeEnabled();
        await user.click(checkbox());
        expect(start()).toBeDisabled();
        expect(POST).not.toHaveBeenCalled();
    });

    it("cannot start when there is nothing to approve", () => {
        setup(0);
        expect(within(dialog()).getByText(bulk.none)).toBeInTheDocument();
        expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
        expect(start()).toBeDisabled();
    });

    it("closes without refreshing when nothing was run", async () => {
        const { user, onClose } = setup();
        await user.click(screen.getByRole("button", { name: bulk.cancel }));
        expect(onClose).toHaveBeenCalledOnce();
        expect(refresh).not.toHaveBeenCalled();
    });
});

describe("BulkApproveDialog run", () => {
    it("runs the calls of the contract, shows the progress and ends with the report", async () => {
        POST.mockResolvedValueOnce(done({ published: 100, remaining: 150, next_cursor: SHA(1) }))
            .mockResolvedValueOnce(
                done({ published: 99, conflicts: [ID(9)], remaining: 50, next_cursor: SHA(2) }),
            )
            .mockResolvedValueOnce(
                done({
                    published: 49,
                    failed: [{ extraction_id: ID(8), reason: "source has a newer extraction" }],
                }),
            );
        const { user } = setup(250);
        await user.click(checkbox());
        await user.click(start());

        await screen.findByRole("button", { name: bulk.report.close });
        const bodies = POST.mock.calls.map(([, init]) => init.body);
        expect(bodies.map((b) => [b.cursor, b.expected_count, b.limit])).toEqual([
            [undefined, 250, 100],
            [SHA(1), 150, 100],
            [SHA(2), 50, 100],
        ]);
        expect(bodies[0]).toMatchObject({ band: "high", filters: { court: "bam" } });
        expect(screen.getByRole("progressbar")).toHaveAttribute("value", "250");
        expect(screen.getByRole("heading", { name: bulk.report.heading.finished })).toHaveFocus();
        expect(screen.getByText("250 / 250")).toBeInTheDocument();
        expect(screen.getByText(messages.enums.bulkFailure.newer_extraction)).toBeInTheDocument();
    });

    it("shows the progress as it grows and cannot be closed while a call is in flight", async () => {
        const first = hold();
        const { user, onClose } = setup(250);
        await user.click(checkbox());
        await user.click(start());

        const bar = screen.getByRole("progressbar");
        expect(bar).toHaveAttribute("max", "250");
        expect(bar).toHaveAttribute("value", "0");
        expect(bar).not.toHaveAttribute("aria-valuenow");
        expect(dialog()).not.toHaveAttribute("aria-busy");
        expect(screen.getByRole("heading", { name: bulk.run.heading })).toHaveFocus();
        expect(screen.getByText("0 / 250")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: bulk.cancel })).not.toBeInTheDocument();
        escape();
        expect(onClose).not.toHaveBeenCalled();

        POST.mockImplementationOnce(() => new Promise(() => {}));
        await first(
            done({ published: 90, conflicts: [ID(1)], remaining: 160, next_cursor: SHA(1) }),
        );
        await waitFor(() => expect(screen.getByText("91 / 250")).toBeInTheDocument());
        expect(bar).toHaveAttribute("value", "91");
        const counters = screen.getByText(bulk.run.published).parentElement;
        expect(counters).toHaveTextContent("90");
        expect(screen.getByText(bulk.run.conflicts).parentElement).toHaveTextContent("1");
        escape();
        expect(onClose).not.toHaveBeenCalled();
    });

    it("stops after the current call, saying so meanwhile, and then may be closed", async () => {
        const first = hold();
        const { user, onClose } = setup(250);
        await user.click(checkbox());
        await user.click(start());
        await user.click(screen.getByRole("button", { name: bulk.run.stop }));

        expect(screen.getByText(bulk.run.stopping)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: bulk.run.stop })).toBeDisabled();
        escape();
        expect(onClose).not.toHaveBeenCalled();

        await first(done({ published: 100, remaining: 150, next_cursor: SHA(1) }));
        await screen.findByText("Durduruldu: 150 kayıt işlenmedi.");
        expect(POST).toHaveBeenCalledTimes(1);
        escape();
        expect(onClose).toHaveBeenCalledOnce();
    });

    it("on a changed queue shows the new count and goes on only after it is confirmed again", async () => {
        POST.mockResolvedValueOnce(done({ published: 100, remaining: 150, next_cursor: SHA(1) }))
            .mockResolvedValueOnce(refused("bulk_count_changed", { total: 140, expected: 150 }))
            .mockResolvedValueOnce(done({ published: 140 }));
        const { user } = setup(250);
        await user.click(checkbox());
        await user.click(start());

        await screen.findByText("Kuyruk değişti: şimdi 140 kayıt var.");
        const resume = screen.getByRole("button", { name: "140 kaydı onaylamaya devam et" });
        expect(resume).toBeDisabled();
        expect(screen.getByLabelText("Bu 140 kaydı kendi adımla onaylıyorum")).not.toBeChecked();
        await user.click(checkbox());
        await user.click(resume);

        await screen.findByRole("button", { name: bulk.report.close });
        expect(POST.mock.calls[2]?.[1].body).toMatchObject({ cursor: SHA(1), expected_count: 140 });
        expect(screen.getByText("240 / 240")).toBeInTheDocument();
    });

    it("on a network error offers the same call again", async () => {
        POST.mockRejectedValueOnce(new TypeError("fetch failed")).mockResolvedValueOnce(
            done({ published: 3 }),
        );
        const { user } = setup(3);
        await user.click(checkbox());
        await user.click(start());

        await screen.findByText(messages.errors.upstream_unavailable);
        await user.click(screen.getByRole("button", { name: bulk.halted.retry }));
        await screen.findByRole("button", { name: bulk.report.close });
        expect(POST).toHaveBeenCalledTimes(2);
        expect(POST.mock.calls[1]?.[1]).toEqual(POST.mock.calls[0]?.[1]);
    });

    it("says a repeated call may already have been applied when it meets a changed queue", async () => {
        POST.mockRejectedValueOnce(new TypeError("fetch failed")).mockResolvedValueOnce(
            refused("bulk_count_changed", { total: 2, expected: 3 }),
        );
        const { user } = setup(3);
        await user.click(checkbox());
        await user.click(start());
        await screen.findByText(messages.errors.upstream_unavailable);
        expect(screen.getByText(bulk.halted.mayHaveApplied)).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: bulk.halted.retry }));

        await screen.findByRole("button", { name: "2 kaydı onaylamaya devam et" });
        expect(screen.getByText(bulk.halted.mayHaveApplied)).toBeInTheDocument();
        expect(screen.queryByText(/Kuyruk değişti: şimdi/)).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: bulk.halted.report }));
        expect(screen.getByText(bulk.report.undercounted)).toBeInTheDocument();
        expect(screen.getByText("Kuyruk değişti: 2 kayıt işlenmedi.")).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: bulk.report.heading.stopped })).toHaveFocus();
    });

    it("reports a run whose queue changed as incomplete, with the new count", async () => {
        POST.mockResolvedValueOnce(
            done({ published: 100, remaining: 150, next_cursor: SHA(1) }),
        ).mockResolvedValueOnce(refused("bulk_count_changed", { total: 140, expected: 150 }));
        const { user } = setup(250);
        await user.click(checkbox());
        await user.click(start());
        await user.click(await screen.findByRole("button", { name: bulk.halted.report }));
        expect(screen.getByText("Kuyruk değişti: 140 kayıt işlenmedi.")).toBeInTheDocument();
        expect(screen.queryByText(bulk.report.undercounted)).not.toBeInTheDocument();
    });

    it("ends as failed when the server does not advance", async () => {
        POST.mockResolvedValueOnce(done({ remaining: 3, next_cursor: SHA(1) }));
        const { user } = setup(3);
        await user.click(checkbox());
        await user.click(start());
        await screen.findByText(new RegExp(messages.errors.bulk_no_progress));
        expect(POST).toHaveBeenCalledTimes(1);
        expect(
            screen.getByRole("heading", { name: bulk.report.heading.failed }),
        ).toBeInTheDocument();
    });

    it("keeps the filters it started with when the props change mid-run", async () => {
        const first = hold();
        const { user, onClose, view } = setup(250);
        await user.click(checkbox());
        await user.click(start());
        view.rerender(element(7, onClose, { ...params, court: "yargitay_daire" }));
        POST.mockResolvedValueOnce(done({ published: 150 }));
        await first(done({ published: 100, remaining: 150, next_cursor: SHA(1) }));
        await screen.findByRole("button", { name: bulk.report.close });
        const bodies = POST.mock.calls.map(([, init]) => init.body);
        expect(bodies.map((b) => [b.filters, b.expected_count])).toEqual([
            [{ court: "bam" }, 250],
            [{ court: "bam" }, 150],
        ]);
    });

    it("ends on a refusal with its translated message and the partial report", async () => {
        POST.mockResolvedValueOnce(refused("bulk_band_not_allowed"));
        const { user } = setup(3);
        await user.click(checkbox());
        await user.click(start());
        await screen.findByText(new RegExp(messages.errors.bulk_band_not_allowed));
        expect(screen.getByText(/3 kayıt işlenmedi/)).toBeInTheDocument();
    });
});

describe("BulkApproveDialog report", () => {
    it("links conflicts and failures to their detail screens with the queue params", async () => {
        POST.mockResolvedValueOnce(
            done({
                published: 1,
                conflicts: [ID(1)],
                failed: [
                    { extraction_id: ID(2), reason: "court and court_level are required" },
                    { extraction_id: ID(3), reason: "a brand new reason" },
                ],
            }),
        );
        const { user } = setup(4);
        await user.click(checkbox());
        await user.click(start());

        const conflict = await screen.findByRole("link", { name: ID(1) });
        expect(conflict).toHaveAttribute(
            "href",
            `/kararlar/${ID(1)}?band=high&court=bam&sort=score_desc&page=2`,
        );
        expect(screen.getByRole("link", { name: ID(2) })).toHaveAttribute(
            "href",
            expect.stringContaining("band=high"),
        );
        expect(screen.getByText(messages.enums.bulkFailure.court_required)).toBeInTheDocument();
        expect(screen.getByText("a brand new reason")).toBeInTheDocument();
    });

    it("lists at most 20 records of a kind and counts the rest", async () => {
        const conflicts = Array.from({ length: 27 }, (_, n) => ID(n + 1));
        POST.mockResolvedValueOnce(done({ conflicts }));
        const { user } = setup(27);
        await user.click(checkbox());
        await user.click(start());
        await screen.findByText("ve 7 daha");
        expect(screen.getAllByRole("link")).toHaveLength(20);
    });

    it("refreshes the queue when the report is closed", async () => {
        POST.mockResolvedValueOnce(done({ published: 2 }));
        const { user, onClose } = setup(2);
        await user.click(checkbox());
        await user.click(start());
        await user.click(await screen.findByRole("button", { name: bulk.report.close }));
        expect(refresh).toHaveBeenCalledOnce();
        expect(onClose).toHaveBeenCalledOnce();
    });
});

describe("BulkApproveDialog on the statute queue", () => {
    const statutes: StatuteQueueParams = {
        kind: "statute",
        statute: "5510",
        band: "high",
        page: 1,
    };
    const articles: BulkSample[] = [
        { id: ID(1), title: "m. 18 · Fesih", esasNo: "", kararNo: "", note: "3 sürüm · 1 boşluk" },
    ];

    function setupStatutes(total = 120, state: StatuteQueueParams = statutes) {
        renderWithIntl(
            <BulkApproveDialog
                onClose={vi.fn()}
                returnFocusTo={{ current: null }}
                params={state}
                total={total}
                sample={articles}
            />,
        );
        return userEvent.setup();
    }

    it("words the confirmation for articles: count, statute, examples, and no decision verification note", () => {
        setupStatutes();
        expect(within(dialog()).getByText("120 madde")).toBeInTheDocument();
        expect(within(dialog()).getByText(bulk.introStatute)).toBeInTheDocument();
        expect(within(dialog()).getByText("Kanun: 5510")).toBeInTheDocument();
        expect(within(dialog()).getByText("Güven: Yüksek")).toBeInTheDocument();
        expect(within(dialog()).getByText("m. 18 · Fesih")).toBeInTheDocument();
        expect(within(dialog()).getByText("3 sürüm · 1 boşluk")).toBeInTheDocument();
        expect(within(dialog()).getByText(bulk.unverifiedStatute)).toBeInTheDocument();
        expect(within(dialog()).queryByText(bulk.unverified)).not.toBeInTheDocument();
    });

    it("shows no search line: the statute scope knows no search", () => {
        setupStatutes(120, { ...statutes, q: "fesih" });
        expect(within(dialog()).getByText("Kanun: 5510")).toBeInTheDocument();
        expect(within(dialog()).queryByText(/Arama/)).not.toBeInTheDocument();
    });

    it("runs the same loop against the statute endpoint with the statute as its scope", async () => {
        POST.mockResolvedValueOnce(
            done({ published: 100, remaining: 20, next_cursor: ID(1) }),
        ).mockResolvedValueOnce(done({ published: 20, conflicts: [ID(7)] }));
        const user = setupStatutes();
        await user.click(checkbox());
        await user.click(start());

        await screen.findByRole("button", { name: bulk.report.close });
        expect(POST.mock.calls.map(([path]) => path)).toEqual([
            "/review/statutes/bulk-approve",
            "/review/statutes/bulk-approve",
        ]);
        const bodies = POST.mock.calls.map(([, init]) => init.body);
        expect(bodies[0]).toEqual({
            band: "high",
            statute: "5510",
            expected_count: 120,
            limit: 100,
        });
        expect(bodies[1]).toEqual({
            band: "high",
            statute: "5510",
            expected_count: 20,
            limit: 100,
            cursor: ID(1),
        });
        // A conflict in the report leads to the statute detail screen with the queue state.
        expect(screen.getByRole("link", { name: ID(7) })).toHaveAttribute(
            "href",
            `/mevzuat/${ID(7)}?kanun=5510&band=high`,
        );
    });
});
