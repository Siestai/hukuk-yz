import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { isUpstreamUnavailable } from "@/lib/api/errors";
import { settle } from "@/lib/api/settle";
import { infoTip, renderWithIntl } from "@/test/intl";
import { QueueResults } from "./queue-results";

const redirect = vi.hoisted(() =>
    vi.fn((path: string) => {
        throw new Error(`NEXT_REDIRECT ${path}`);
    }),
);
vi.mock("next/navigation", () => ({ redirect }));

const answer = (status: number, body: { data?: unknown; error?: unknown } = {}) =>
    Promise.resolve({ response: new Response(null, { status }), ...body });
const list = (data: unknown) => settle(answer(200, { data }) as never, "list");
const item = {
    extraction_id: "e1",
    source_id: "s1",
    title: "KIDEM TAZMİNATI",
    court: "yargitay",
    chamber: "9. HD",
    esas_no: "2019/1234",
    karar_no: "2021/567",
    decision_date: "2021-03-05",
    journal_issue: 61,
    band: "low",
    score: 40,
    reasons: ["missing_karar_no"],
    duplicate_group: null,
} as const;
const base = { sort: "score_asc", page: 1 } as const;

async function renderResults(params: Parameters<typeof QueueResults>[0]["params"], data: unknown) {
    renderWithIntl(await QueueResults({ params, list: list(data) as never }));
}

describe("QueueResults", () => {
    it("shows the table and the pagination", async () => {
        await renderResults(base, { total: 310, items: [item] });
        expect(within(screen.getByRole("table")).getByText("KIDEM TAZMİNATI")).toBeInTheDocument();
        expect(screen.getByText("1-50 / 310")).toBeInTheDocument();
    });

    it("says nothing is pending when the queue is empty", async () => {
        await renderResults(base, { total: 0, items: [] });
        expect(screen.getByText(messages.review.queue.empty.none)).toBeInTheDocument();
    });

    it("says no record matches when filters leave nothing", async () => {
        await renderResults({ ...base, q: "zzz" }, { total: 0, items: [] });
        expect(screen.getByText(messages.review.queue.empty.filtered)).toBeInTheDocument();
    });

    it("offers the first page when the page is past the last", async () => {
        await renderResults({ ...base, band: "low", page: 7 }, { total: 310, items: [] });
        expect(screen.getByText(messages.review.queue.empty.pastEnd)).toBeInTheDocument();
        expect(
            screen.getByRole("link", { name: messages.review.queue.empty.firstPage }),
        ).toHaveAttribute("href", "/?band=low");
    });

    it("shows the translated message of a 4xx error code inline", async () => {
        const failed = settle(
            answer(422, { error: { error: { code: "validation_error", params: {} } } }) as never,
            "list",
        );
        renderWithIntl(await QueueResults({ params: base, list: failed as never }));
        expect(screen.getByRole("alert")).toHaveTextContent(messages.errors.validation_error);
    });

    it("goes to sign-in again when the session is gone", async () => {
        const gone = settle(answer(401) as never, "list");
        await expect(QueueResults({ params: base, list: gone as never })).rejects.toThrow(
            "NEXT_REDIRECT /oturum-sonu",
        );
    });

    it.each([
        ["answers 5xx", () => answer(503)],
        ["cannot be reached", () => Promise.reject(new TypeError("fetch failed"))],
    ])("raises upstream_unavailable when the list %s", async (_name, request) => {
        const down = settle(request() as never, "list");
        const error = await QueueResults({ params: base, list: down as never }).catch(
            (e: Error) => e,
        );
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
    });
});

describe("QueueResults help", () => {
    it("has the one card list tip next to the cards", async () => {
        await renderResults(base, { total: 1, items: [item] });
        expect(infoTip(messages.review.queue.table.cardsTopic)).toBeInTheDocument();
    });
});
