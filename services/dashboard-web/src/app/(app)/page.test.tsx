import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formats } from "../../i18n/formats";
import messages from "../../../messages/tr.json";
import { isUpstreamUnavailable } from "@/lib/api/errors";
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
        expect(screen.getByText("12")).toBeInTheDocument();
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

    it("keeps the bulk approve button visible and disabled", async () => {
        get.mockResolvedValue(ok({ total: 1, items: [item] }));
        await renderPage();
        expect(
            screen.getByRole("button", { name: messages.review.queue.bulkApprove }),
        ).toBeDisabled();
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
