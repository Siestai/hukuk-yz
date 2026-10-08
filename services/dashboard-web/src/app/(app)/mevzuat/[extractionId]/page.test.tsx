import { render, screen, within } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../../../messages/tr.json";
import { formats, timeZone } from "@/i18n/formats";
import { detail, STATUTE_ID } from "@/test/statute-fixtures";
import StatuteArticlePage from "./page";

const get = vi.fn();
const notFound = vi.hoisted(() =>
    vi.fn(() => {
        throw new Error("NEXT_NOT_FOUND");
    }),
);
vi.mock("@/lib/api/server", () => ({ createServerApi: async () => ({ GET: get }) }));
vi.mock("next/navigation", () => ({
    notFound,
    redirect: vi.fn(),
    useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

const ok = (data: unknown) => ({ response: new Response(null, { status: 200 }), data });
const failed = (status: number, code?: string) => ({
    response: new Response(null, { status }),
    error: code ? { error: { code, params: {} } } : undefined,
});

async function renderPage(search: Record<string, string> = {}, id = STATUTE_ID) {
    render(
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {await StatuteArticlePage({
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

describe("StatuteArticlePage", () => {
    it("shows the article, how recent the text is, and why the band is what it is, in plain words", async () => {
        await renderPage({ kanun: "4857" });
        expect(
            screen.getByRole("heading", {
                level: 1,
                name: "4857 · m. 18 · Feshin geçerli sebebe dayandırılması",
            }),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Metin 22.04.2026 tarihli kopyaya kadar güncel."),
        ).toBeInTheDocument();
        const card = screen
            .getByText(messages.review.statutes.confidence.title)
            .closest("div[data-slot='card']") as HTMLElement;
        expect(
            within(card).getByText(messages.enums.statuteWarning.before_earliest_snapshot),
        ).toBeInTheDocument();
        // A reason is not repeated among the other warnings.
        expect(
            within(card).getAllByText(messages.enums.statuteWarning.exception_effective),
        ).toHaveLength(1);
        expect(
            within(card).getByText(messages.enums.statuteWarning.footnote_marker_not_found),
        ).toBeInTheDocument();
    });

    it("shows the timeline and the actions of a pending article, without edit", async () => {
        await renderPage();
        expect(
            screen.getByRole("list", { name: messages.review.statutes.timeline.label }),
        ).toBeInTheDocument();
        expect(screen.getByText(messages.review.statutes.timeline.gapNoText)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /^Onayla/ })).toBeEnabled();
        expect(screen.queryByRole("button", { name: /Düzelt/ })).not.toBeInTheDocument();
    });

    it("has no actions for a published article and names its outcome", async () => {
        get.mockResolvedValue(
            ok({
                ...detail,
                status: "approved",
                reviews: [
                    {
                        id: "r1",
                        reviewer_id: "u1",
                        reviewer_name: "Baran",
                        decision: "approve",
                        edits: null,
                        note: null,
                        reviewed_at: "2026-10-07T09:30:00Z",
                    },
                ],
            }),
        );
        await renderPage();
        expect(screen.queryByRole("button", { name: /^Onayla/ })).not.toBeInTheDocument();
        expect(
            screen.getByRole("region", { name: messages.review.detail.statusStrip.label }),
        ).toHaveTextContent("Baran");
        expect(screen.getByText(messages.review.detail.history.title)).toBeInTheDocument();
    });

    it("links to the extraction whose text is the published one", async () => {
        get.mockResolvedValue(ok({ ...detail, live_extraction_id: "live-1" }));
        await renderPage({ kanun: "5510" });
        expect(
            screen.getByRole("link", { name: messages.review.statutes.detail.liveLink }),
        ).toHaveAttribute("href", "/mevzuat/live-1?kanun=5510");
    });

    it("goes back to the queue with its filters", async () => {
        await renderPage({ kanun: "5510", band: "high" });
        expect(
            screen.getByRole("link", { name: messages.review.statutes.detail.back }),
        ).toHaveAttribute("href", "/mevzuat?kanun=5510&band=high");
    });

    it("is a 404 for a decision's id, a malformed id, and raises on other API errors", async () => {
        get.mockResolvedValue(failed(404, "extraction_not_found"));
        await expect(renderPage()).rejects.toThrow("NEXT_NOT_FOUND");
        await expect(renderPage({}, "not-a-uuid")).rejects.toThrow("NEXT_NOT_FOUND");
        get.mockResolvedValue(failed(422, "validation_error"));
        await expect(renderPage()).rejects.toThrow("answered validation_error");
    });
});
