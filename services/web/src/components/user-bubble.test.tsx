import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ClarificationQuestion, Turn } from "@/lib/chat-types";
import { renderWithIntl } from "@/test/intl";
import { UserBubble } from "./user-bubble";

const questions = [
    {
        id: "q1",
        fact_key: "tutanak_tarihi",
        text: "Tutanak hangi tarihte tutuldu?",
        why: "",
        source_refs: [],
        input: { kind: "date", options: [{ value: "yok", label: "Tutanak tutulmadı" }] },
    },
] as unknown as ClarificationQuestion[];

function bubble(value: string) {
    const turn = {
        clarification_answers: [{ question_id: "q1", value, unknown: false }],
    } as unknown as Turn;
    renderWithIntl(<UserBubble turn={turn} questions={questions} />);
}

describe("UserBubble", () => {
    it("echoes a date answer as DD.MM.YYYY", () => {
        bubble("2026-10-03");
        expect(screen.getByText("Tutanak hangi tarihte tutuldu? 03.10.2026")).toBeInTheDocument();
    });

    it("echoes the no-date option by its label", () => {
        bubble("yok");
        expect(
            screen.getByText("Tutanak hangi tarihte tutuldu? Tutanak tutulmadı"),
        ).toBeInTheDocument();
    });
});
