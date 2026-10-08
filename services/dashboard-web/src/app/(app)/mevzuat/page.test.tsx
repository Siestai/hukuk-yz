import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formats } from "../../../i18n/formats";
import messages from "../../../../messages/tr.json";
import { listItem } from "@/test/statute-fixtures";
import StatuteQueuePage from "./page";

const get = vi.fn();
const redirect = vi.hoisted(() =>
    vi.fn((path: string) => {
        throw new Error(`NEXT_REDIRECT ${path}`);
    }),
);
vi.mock("@/lib/api/server", () => ({ createServerApi: async () => ({ GET: get }) }));
vi.mock("@/components/statute-review/statute-results", () => ({
    StatuteResults: () => <p>statute results</p>,
}));
vi.mock("@/components/statute-review/statute-bulk-approve", () => ({
    StatuteBulkApprove: ({ params, list }: { params: { statute: string }; list?: unknown }) => (
        <p>{`bulk approve ${params.statute} ${list ? "with list" : "without list"}`}</p>
    ),
}));
vi.mock("next/navigation", () => ({
    redirect,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
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
const row = (statute_number: string, band: string, status: string, count: number) => ({
    statute_number,
    band,
    status,
    count,
});
const summary = {
    items: [
        row("4857", "high", "pending", 200),
        row("4857", "medium", "pending", 30),
        row("4857", "low", "pending", 8),
        row("4857", "high", "approved", 12),
        row("4857", "low", "rejected", 3),
        row("5510", "medium", "pending", 90),
    ],
};

async function renderPage(search: Record<string, string> = {}) {
    render(
        <NextIntlClientProvider locale="tr" messages={messages} formats={formats}>
            {await StatuteQueuePage({ searchParams: Promise.resolve(search) })}
        </NextIntlClientProvider>,
    );
}

beforeEach(() => {
    get.mockReset();
    get.mockImplementation(async (path: string) =>
        path === "/review/statutes/summary" ? ok(summary) : ok({ total: 1, items: [listItem] }),
    );
    redirect.mockClear();
});

const { statutes } = messages.review;

describe("StatuteQueuePage", () => {
    it("shows the title, the waiting total of the statute, the summary cards and the results", async () => {
        await renderPage();
        expect(screen.getByRole("heading", { level: 1, name: statutes.title })).toBeInTheDocument();
        expect(screen.getByText("238 madde onay bekliyor")).toBeInTheDocument();
        expect(screen.getByText("statute results")).toBeInTheDocument();
        expect(screen.getByText(messages.review.queue.summary.bandTitle)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Yüksek/ })).toHaveAttribute(
            "href",
            "/mevzuat?band=high",
        );
    });

    it("counts the waiting articles of each statute in the statute tabs", async () => {
        await renderPage();
        const nav = screen.getByRole("navigation", { name: statutes.statuteTabs.label });
        expect(nav).toHaveTextContent("4857 İş Kanunu238");
        expect(nav).toHaveTextContent("5510 SGK Kanunu90");
    });

    it("switches to the other statute: its counts, its query and its bulk scope", async () => {
        await renderPage({ kanun: "5510", band: "high" });
        expect(screen.getByText("90 madde onay bekliyor")).toBeInTheDocument();
        expect(screen.getByText("bulk approve 5510 with list")).toBeInTheDocument();
        expect(get).toHaveBeenCalledWith("/review/statutes", {
            params: {
                query: {
                    status: undefined,
                    band: "high",
                    statute: "5510",
                    q: undefined,
                    limit: 50,
                    offset: 0,
                },
            },
        });
    });

    it("shows the status tabs with the counts of the statute", async () => {
        await renderPage();
        const nav = screen.getByRole("navigation", {
            name: messages.review.queue.tabs.labelStatute,
        });
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.approved}12`);
        expect(nav).toHaveTextContent(`${messages.review.queue.tabs.all}253`);
    });

    it.each([
        ["onaylanan", "approved", "12 madde yayında", "Yayındaki maddeler"],
        ["reddedilen", "rejected", "3 madde reddedildi", "Reddedilen maddeler"],
        ["tumu", "all", "253 madde: 238 bekliyor, 12 yayında, 3 reddedildi", "Tüm maddeler"],
    ])(
        "the %s tab has its own heading, no bulk approve and no summary cards",
        async (slug, status, subtitle, title) => {
            await renderPage({ durum: slug });
            expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
            expect(screen.getByText(subtitle)).toBeInTheDocument();
            expect(screen.queryByText(/bulk approve/)).toBeNull();
            expect(screen.queryByText(messages.review.queue.summary.bandTitle)).toBeNull();
            expect(get).toHaveBeenCalledWith("/review/statutes", {
                params: { query: expect.objectContaining({ status }) },
            });
        },
    );

    it("shows the translated message of a 4xx summary error instead of the results", async () => {
        get.mockImplementation(async (path: string) =>
            path === "/review/statutes/summary"
                ? failed(403, "forbidden")
                : ok({ total: 0, items: [] }),
        );
        await renderPage();
        expect(screen.getByRole("alert")).toHaveTextContent(messages.errors.forbidden);
        expect(screen.queryByText("statute results")).toBeNull();
    });

    it("goes to sign-in again when the session is gone", async () => {
        get.mockResolvedValue(failed(401, "unauthorized"));
        await expect(StatuteQueuePage({ searchParams: Promise.resolve({}) })).rejects.toThrow(
            "NEXT_REDIRECT /oturum-sonu",
        );
    });
});
