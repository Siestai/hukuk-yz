import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Turn } from "@/lib/chat-types";
import { conditionalAnswer } from "@/test/answer-fixture";
import { renderWithIntl } from "@/test/intl";
import { Thread } from "./thread";

describe("Thread", () => {
    it("opens each answer's citation with that answer's law date", async () => {
        const onOpenCitation = vi.fn();
        const turns = ["2020-01-01", "2026-10-01"].map((date, index) => ({
            id: String(index),
            role: "assistant",
            created_at: date,
            answer: { ...conditionalAnswer, applied_law_date: date },
        })) as Turn[];
        renderWithIntl(
            <Thread
                turns={turns}
                live={null}
                partial={null}
                failure={null}
                mode="short"
                onSend={vi.fn()}
                onRetry={vi.fn()}
                onOpenCitation={onOpenCitation}
            />,
        );
        const links = screen.getAllByRole("button", { name: /Dayanağı aç/ });
        await userEvent.click(links[0]!);
        expect(onOpenCitation).toHaveBeenLastCalledWith(expect.anything(), "2020-01-01");
        await userEvent.click(links.at(-1)!);
        expect(onOpenCitation).toHaveBeenLastCalledWith(expect.anything(), "2026-10-01");
    });

    it("uses the clarification turn's event date for its sources", async () => {
        const onOpenCitation = vi.fn();
        const citation = conditionalAnswer.points[0]!.citations[0]!;
        const turns = [
            {
                id: "clarify",
                role: "assistant",
                created_at: "2026-10-01",
                facts: { title: "Olay", facts: [], event_date: "2020-01-01" },
                clarification: {
                    questions: [
                        {
                            id: "q1",
                            text: "Soru",
                            why: "Neden",
                            fact_key: "a",
                            source_refs: [citation],
                            input: { kind: "choice", options: [] },
                        },
                    ],
                },
            },
        ] as unknown as Turn[];
        renderWithIntl(
            <Thread
                turns={turns}
                live={null}
                partial={null}
                failure={null}
                mode="short"
                onSend={vi.fn()}
                onRetry={vi.fn()}
                onOpenCitation={onOpenCitation}
            />,
        );
        await userEvent.click(screen.getByRole("button", { name: /Dayanağı aç/ }));
        expect(onOpenCitation).toHaveBeenCalledWith(citation, "2020-01-01");
    });

    it.each([false, true])("offers recovery for a failed reply, restart=%s", async (restart) => {
        const onRetry = vi.fn();
        renderWithIntl(
            <Thread
                turns={[]}
                live={null}
                partial={null}
                failure={{ code: "clarification_not_pending", params: {}, restart }}
                mode="short"
                onSend={vi.fn()}
                onRetry={onRetry}
                onOpenCitation={vi.fn()}
            />,
        );
        await userEvent.click(
            screen.getByRole("button", {
                name: restart ? "Netleştirmeyi yeniden başlat" : "Tekrar dene",
            }),
        );
        expect(onRetry).toHaveBeenCalledOnce();
        if (restart)
            expect(screen.getByText(/bilgileri tekrar girebilirsiniz/)).toBeInTheDocument();
    });
});

it("shows honest source insufficiency without connection recovery", () => {
    renderWithIntl(
        <Thread
            turns={[]}
            live={null}
            partial={null}
            failure={{ code: "answer_not_verified", params: {}, retryable: false }}
            mode="short"
            onSend={vi.fn()}
            onRetry={vi.fn()}
            onOpenCitation={vi.fn()}
        />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
        "Kaynaklar doğrulanmış bir yanıt oluşturmak için yetersiz.",
    );
    expect(screen.queryByText(/Bağlantı koptu/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Tekrar dene" })).not.toBeInTheDocument();
});

it.each(["internal_error", "chat_unavailable", "upstream_unavailable"])(
    "hides recovery for completed error %s",
    (code) => {
        renderWithIntl(
            <Thread
                turns={[]}
                live={null}
                partial={null}
                failure={{ code, params: {}, retryable: false }}
                mode="short"
                onSend={vi.fn()}
                onRetry={vi.fn()}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.getByRole("alert")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Tekrar dene" })).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Netleştirmeyi yeniden başlat" }),
        ).not.toBeInTheDocument();
    },
);
