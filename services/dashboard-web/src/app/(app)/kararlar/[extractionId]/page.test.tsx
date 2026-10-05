import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../../../messages/tr.json";
import { formats, timeZone } from "@/i18n/formats";
import { isUpstreamUnavailable } from "@/lib/api/errors";
import DecisionPage from "./page";

const ID = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
const get = vi.fn();
const notFound = vi.hoisted(() =>
    vi.fn(() => {
        throw new Error("NEXT_NOT_FOUND");
    }),
);
const redirect = vi.hoisted(() =>
    vi.fn((path: string) => {
        throw new Error(`NEXT_REDIRECT ${path}`);
    }),
);
vi.mock("@/lib/api/server", () => ({ createServerApi: async () => ({ GET: get }) }));
vi.mock("next/navigation", () => ({
    notFound,
    redirect,
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

const ok = (data: unknown) => ({ response: new Response(null, { status: 200 }), data });
const failed = (status: number, code?: string) => ({
    response: new Response(null, { status }),
    error: code ? { error: { code, params: {} } } : undefined,
});

const detail = {
    extraction_id: ID,
    source_id: "s1",
    source_status: "analyzed",
    title: "KIDEM TAZMİNATI",
    fields: {
        court: "yargitay",
        court_level: "daire",
        chamber: "9. HD",
        esas_no: "2019/1234",
        karar_no: "2021/567",
        decision_date: "2021-03-05",
        related_articles: [{ statute: 4857, label: "4857 SK", articles: ["18"], raw: "" }],
        outcome: "onama",
        keywords: ["fesih"],
        journal_issue: 61,
        full_text: "Karar metni.",
        editorial_summary: "Dergi özeti.",
    },
    warnings: ["invalid_date"],
    confidence: { score: 40, band: "low", reasons: ["missing_karar_no"] },
    raw_text_ref: null,
    pdf: "available",
    duplicates: [{ extraction_id: "d1", band: "low", score: 40, text_length: 900 }],
    reviews: [
        {
            id: "r1",
            reviewer_id: "u1",
            reviewer_name: "Baran",
            decision: "approve",
            edits: null,
            note: null,
            reviewed_at: "2026-10-02T09:00:00Z",
        },
    ],
};

async function renderPage(id = ID, search: Record<string, string> = {}) {
    render(
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {await DecisionPage({
                params: Promise.resolve({ extractionId: id }),
                searchParams: Promise.resolve(search),
            })}
        </NextIntlClientProvider>,
    );
}

beforeEach(() => {
    get.mockReset();
    notFound.mockClear();
    get.mockResolvedValue(ok(detail));
});

describe("DecisionPage", () => {
    it("asks the API for the extraction and shows title, fields, confidence, history and the tabs", async () => {
        await renderPage();
        expect(get).toHaveBeenCalledWith("/review/decisions/{extraction_id}", {
            params: { path: { extraction_id: ID } },
        });
        expect(
            screen.getByRole("heading", { level: 1, name: "KIDEM TAZMİNATI" }),
        ).toBeInTheDocument();
        expect(screen.getByText("4857 s. Kanun m. 18")).toBeInTheDocument();
        expect(screen.getByText("05.03.2021")).toBeInTheDocument();
        expect(screen.getByText(messages.enums.reason.missing_karar_no)).toBeInTheDocument();
        expect(screen.getByText(messages.enums.warning.invalid_date)).toBeInTheDocument();
        expect(screen.getByText("Baran")).toBeInTheDocument();
        expect(
            screen.getByRole("tab", { name: messages.review.detail.tabPdf }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("tab", { name: messages.review.detail.tabText }),
        ).toBeInTheDocument();
        expect(screen.getByTitle(messages.review.detail.pdf.title)).toHaveAttribute(
            "src",
            `/api/review/decisions/${ID}/file`,
        );
        expect(screen.getByText("Karar metni.", { selector: "article p" })).toBeInTheDocument();
        expect(screen.queryByRole("note")).toBeNull();
    });

    it("keeps the queue filters in the back link and the duplicate links", async () => {
        await renderPage(ID, { band: "low", court: "yargitay", page: "2", ignored: "x" });
        expect(screen.getByRole("link", { name: messages.review.detail.back })).toHaveAttribute(
            "href",
            "/?band=low&court=yargitay&page=2",
        );
        expect(screen.getByRole("link", { name: /Metin uzunluğu 900/ })).toHaveAttribute(
            "href",
            "/kararlar/d1?band=low&court=yargitay&page=2",
        );
    });

    it("tells once, in the status strip, that actions are unavailable for a record that left the queue", async () => {
        get.mockResolvedValue(ok({ ...detail, source_status: "rejected" }));
        await renderPage();
        expect(screen.queryByRole("note")).toBeNull();
        expect(screen.getAllByText(messages.review.detail.statusStrip.unavailable)).toHaveLength(1);
    });

    it("hides the duplicates card without duplicates", async () => {
        get.mockResolvedValue(ok({ ...detail, duplicates: [] }));
        await renderPage();
        expect(screen.queryByText(messages.review.detail.duplicates.title)).toBeNull();
    });

    it("is a 404 for an id that is not a UUID, without calling the API", async () => {
        await expect(renderPage("12345")).rejects.toThrow("NEXT_NOT_FOUND");
        expect(get).not.toHaveBeenCalled();
    });

    it("is a 404 for extraction_not_found", async () => {
        get.mockResolvedValue(failed(404, "extraction_not_found"));
        await expect(renderPage()).rejects.toThrow("NEXT_NOT_FOUND");
    });

    it("sends a lost session to the sign-out route", async () => {
        get.mockResolvedValue(failed(401, "unauthorized"));
        await expect(renderPage()).rejects.toThrow("NEXT_REDIRECT /oturum-sonu");
    });

    it("shows the empty state instead of a frame when the PDF is missing or not a PDF", async () => {
        get.mockResolvedValue(ok({ ...detail, pdf: "missing" }));
        await renderPage();
        expect(screen.getByText(messages.review.detail.pdf.missing)).toBeInTheDocument();
        expect(screen.queryByTitle(messages.review.detail.pdf.title)).toBeNull();
    });

    it("throws for an API error that is not a 404 of the record, for the error boundary", async () => {
        get.mockResolvedValue(failed(500, "internal_error"));
        const error = await renderPage().catch((e: Error) => e);
        expect(error).toBeInstanceOf(Error);
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
        expect(notFound).not.toHaveBeenCalled();
        get.mockResolvedValue(failed(422, "validation_error"));
        await expect(renderPage()).rejects.toThrow(/validation_error/);
        expect(notFound).not.toHaveBeenCalled();
    });

    it("lets the error page handle a server failure and any other API error", async () => {
        get.mockResolvedValue(failed(500));
        const error = await renderPage().catch((e: Error) => e);
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
        get.mockResolvedValue(failed(403, "forbidden"));
        await expect(renderPage()).rejects.toThrow(/forbidden/);
        expect(notFound).not.toHaveBeenCalled();
    });
});
