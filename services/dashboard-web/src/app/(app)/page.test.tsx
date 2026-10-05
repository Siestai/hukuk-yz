import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formats } from "../../i18n/formats";
import messages from "../../../messages/tr.json";
import { isUpstreamUnavailable } from "@/lib/api/errors";
import { infoTip } from "@/test/intl";
import QueuePage from "./page";

const get = vi.fn();
const summaryGet = vi.fn();
const redirect = vi.hoisted(() =>
    vi.fn((path: string) => {
        throw new Error(`NEXT_REDIRECT ${path}`);
    }),
);
vi.mock("@/lib/api/server", () => ({ createServerApi: async () => ({ GET: get }) }));
vi.mock("@/lib/api/review", () => ({ getReviewSummary: () => summaryGet() }));
vi.mock("@/components/review-queue/queue-results", () => ({
    QueueResults: () => <p>queue results</p>,
}));
vi.mock("@/components/review-queue/queue-bulk-approve", () => ({
    QueueBulkApprove: ({ params, list }: { params: { band?: string }; list?: unknown }) => (
        <p>{`bulk approve ${params.band ?? "any"} ${list ? "with list" : "without list"}`}</p>
    ),
}));
vi.mock("next/navigation", () => ({
    redirect,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next-intl/server", async () => {
    const intl = await import("next-intl");
    return {
        getTranslations: async (ns: string) =>
            intl.createTranslator({ locale: "tr", messages, namespace: ns as never }),
    };
});

const ok = (data: unknown) => ({ response: new Response(null, { status: 200 }), data });
const failed = (status: number, code?: string) => ({
    response: new Response(null, { status }),
    error: code ? { error: { code, params: {} } } : undefined,
});
const summary = {
    by_band: { high: 5906, medium: 101, low: 310 },
    by_court: { yargitay: 6000, "": 17 },
    top_reasons: [{ reason: "missing_karar_no", count: 135 }],
    approved: 12,
    rejected: 3,
};
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
};

async function renderPage(search: Record<string, string> = {}) {
    render(
        <NextIntlClientProvider locale="tr" messages={messages} formats={formats}>
            {await QueuePage({ searchParams: Promise.resolve(search) })}
        </NextIntlClientProvider>,
    );
}

beforeEach(() => {
    get.mockReset();
    summaryGet.mockReset();
    redirect.mockClear();
    summaryGet.mockResolvedValue(ok(summary));
});

describe("QueuePage", () => {
    it("shows the title, the pending total, the summary and the results", async () => {
        get.mockResolvedValue(ok({ total: 310, items: [item] }));
        await renderPage({ band: "low" });
        expect(
            screen.getByRole("heading", { level: 1, name: messages.review.queue.title }),
        ).toBeInTheDocument();
        expect(screen.getByText("6.317 karar onay bekliyor")).toBeInTheDocument();
        expect(screen.getByText("queue results")).toBeInTheDocument();
        // the approved count is in the "Onaylanan" tab and in the results card
        expect(screen.getAllByText("12")).toHaveLength(2);
    });

    it("links the summary to the filters it stands for", async () => {
        get.mockResolvedValue(ok({ total: 310, items: [item] }));
        await renderPage({ band: "low", sort: "score_desc" });
        expect(screen.getByRole("link", { name: /Orta/ })).toHaveAttribute(
            "href",
            "/?band=medium&sort=score_desc",
        );
        expect(screen.getByRole("link", { name: /Düşük/ })).toHaveAttribute("aria-current", "true");
    });

    it("shows the translated message of a 4xx summary error instead of the results", async () => {
        get.mockResolvedValue(ok({ total: 0, items: [] }));
        summaryGet.mockResolvedValue(failed(422, "validation_error"));
        await renderPage();
        expect(screen.getByRole("alert")).toHaveTextContent(messages.errors.validation_error);
        expect(screen.queryByText("queue results")).toBeNull();
    });

    it("passes the URL state to the API as the query", async () => {
        get.mockResolvedValue(ok({ total: 0, items: [] }));
        await renderPage({
            band: "low",
            court: "unknown",
            q: "2019",
            sort: "score_desc",
            page: "3",
            bogus: "x",
        });
        expect(get).toHaveBeenCalledWith("/review/decisions", {
            params: {
                query: {
                    band: "low",
                    court: "",
                    reason: undefined,
                    journal_issue: undefined,
                    q: "2019",
                    sort: "score_desc",
                    limit: 50,
                    offset: 100,
                },
            },
        });
    });

    it("hands the bulk approve button the filters and the list on screen", async () => {
        get.mockResolvedValue(ok({ total: 1, items: [item] }));
        await renderPage({ band: "high" });
        expect(screen.getByText("bulk approve high with list")).toBeInTheDocument();
    });

    it("shows the status tabs with the counts of the summary", async () => {
        get.mockResolvedValue(ok({ total: 1, items: [item] }));
        await renderPage();
        const nav = screen.getByRole("navigation", { name: messages.review.queue.tabs.label });
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.pending}6.317`);
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.approved}12`);
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.rejected}3`);
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.all}6.332`);
    });

    it.each([
        ["onaylanan", "approved", "12 karar onaylandı", "Onaylanan kararlar"],
        ["reddedilen", "rejected", "3 karar reddedildi", "Reddedilen kararlar"],
        ["tumu", "all", "6.332 karar: 6.317 bekliyor, 12 onaylandı, 3 reddedildi", "Tüm kararlar"],
    ])(
        "the %s tab has its own heading and subtitle, no bulk approve and no summary cards",
        async (slug, status, subtitle, title) => {
            get.mockResolvedValue(ok({ total: 1, items: [item] }));
            await renderPage({ durum: slug });
            expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
            expect(screen.getByText(subtitle)).toBeInTheDocument();
            expect(screen.queryByText(/bulk approve/)).toBeNull();
            expect(screen.queryByText(messages.review.queue.summary.bandTitle)).toBeNull();
            expect(screen.queryByText(messages.review.queue.summary.totalsTitle)).toBeNull();
            expect(get).toHaveBeenCalledWith("/review/decisions", {
                params: { query: expect.objectContaining({ status }) },
            });
        },
    );

    it("asks the API for the newest review first in the reviewed tabs", async () => {
        get.mockResolvedValue(ok({ total: 0, items: [] }));
        await renderPage({ durum: "reddedilen" });
        expect(get).toHaveBeenCalledWith("/review/decisions", {
            params: { query: expect.objectContaining({ sort: "reviewed_desc" }) },
        });
    });

    it("goes to sign-in again when the session is gone", async () => {
        summaryGet.mockResolvedValue(failed(401, "unauthorized"));
        await expect(QueuePage({ searchParams: Promise.resolve({}) })).rejects.toThrow(
            "NEXT_REDIRECT /oturum-sonu",
        );
    });

    it("raises upstream_unavailable when the summary answers 5xx", async () => {
        get.mockResolvedValue(ok({ total: 0, items: [] }));
        summaryGet.mockResolvedValue(failed(500));
        const error = await QueuePage({ searchParams: Promise.resolve({}) }).catch((e: Error) => e);
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
    });
});

describe("QueuePage help", () => {
    it("has tips on the title and the pending count, and the welcome card above them", async () => {
        get.mockResolvedValue(ok({ total: 310, items: [item] }));
        await renderPage();
        const { title, subtitle, welcome } = messages.review.queue;
        expect(infoTip(title)).toBeInTheDocument();
        expect(infoTip(subtitle.replace("{total, number}", "6.317"))).toBeInTheDocument();
        expect(
            screen.getByRole("region", {
                name: welcome.title.replace("{brand}", messages.brand.name),
            }),
        ).toBeInTheDocument();
        expect(screen.getByRole("button", { name: welcome.toggle })).toBeInTheDocument();
    });
});
