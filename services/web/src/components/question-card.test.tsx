import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Clarification } from "@/lib/chat-types";
import { renderWithIntl } from "@/test/intl";
import { clarificationReply, QuestionCard } from "./question-card";

const clarification = {
    questions: [
        {
            id: "q1",
            fact_key: "a",
            text: "Kaç işçi çalışıyor?",
            why: "Otuz işçi sınırı için.",
            source_refs: [],
            input: { kind: "choice", options: [{ value: "30+", label: "30 veya fazla" }] },
        },
        {
            id: "q2",
            fact_key: "b",
            text: "Fesih tarihi nedir?",
            why: "Süre için.",
            source_refs: [],
            input: { kind: "date" },
        },
        {
            id: "q3",
            fact_key: "c",
            text: "Kıdem kaç yıl?",
            why: "Kıdem için.",
            source_refs: [],
            input: { kind: "number" },
        },
    ],
} as unknown as Clarification;

function setup() {
    const onReply = vi.fn();
    renderWithIntl(
        <QuestionCard
            clarification={clarification}
            busy={false}
            onReply={onReply}
            onOpenCitation={vi.fn()}
        />,
    );
    return onReply;
}

describe("QuestionCard", () => {
    it("shows one question at a time with its progress and reason", async () => {
        setup();
        expect(screen.getByText("Soru 1 / 3", { selector: "p" })).toBeInTheDocument();
        expect(screen.getByText("Neden soruyorum: Otuz işçi sınırı için.")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "30 veya fazla" }));
        expect(screen.getByText("Soru 2 / 3", { selector: "p" })).toBeInTheDocument();
    });

    it("sends the answers given and Bilmiyorum for the questions skipped", async () => {
        const onReply = setup();
        await userEvent.click(screen.getByRole("button", { name: "30 veya fazla" }));
        await userEvent.click(
            screen.getByRole("button", { name: "Soruları atla, koşullu cevabı göster" }),
        );
        expect(onReply).toHaveBeenCalledWith({
            clarification_answers: [
                { question_id: "q1", value: "30+", unknown: false },
                { question_id: "q2", unknown: true },
                { question_id: "q3", unknown: true },
            ],
        });
    });

    it("skips outright when nothing was answered", async () => {
        const onReply = setup();
        await userEvent.click(
            screen.getByRole("button", { name: "Soruları atla, koşullu cevabı göster" }),
        );
        expect(onReply).toHaveBeenCalledWith({ skip: true });
    });

    it("takes a date typed in", async () => {
        const onReply = setup();
        await userEvent.click(screen.getByRole("button", { name: "Bilmiyorum" }));
        await userEvent.type(screen.getByLabelText("Fesih tarihi nedir?"), "2026-03-01");
        await userEvent.click(screen.getByRole("button", { name: "Devam" }));
        expect(screen.getByText("Soru 3 / 3", { selector: "p" })).toBeInTheDocument();
        expect(onReply).not.toHaveBeenCalled();
    });
});

describe("clarificationReply", () => {
    it("is a skip without answers", () => {
        expect(clarificationReply(clarification.questions, {})).toEqual({ skip: true });
    });
});
