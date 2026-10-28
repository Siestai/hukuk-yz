import { describe, expect, it } from "vitest";

import { conditionalAnswer } from "@/test/answer-fixture";
import { answerPlainText } from "./answer-text";

const labels = { basis: "Dayanak", conditional: "Koşullu cevap", missing: "Eksik bilgiler" };

describe("answerPlainText", () => {
    const text = answerPlainText(conditionalAnswer, labels);

    it("starts with the headline and ends with the disclaimer", () => {
        expect(text.startsWith(conditionalAnswer.headline)).toBe(true);
        expect(text.endsWith("Hukuki görüş değildir.")).toBe(true);
    });

    it("puts the source of a point on its own line", () => {
        const first = conditionalAnswer.points[0]!;
        expect(text).toContain(`- ${first.text}\n  Dayanak: ${first.citations[0]!.label}`);
    });

    it("names the note of a conditional answer and lists the missing information", () => {
        expect(text).toContain(`Koşullu cevap: ${conditionalAnswer.status_note}`);
        expect(text).toContain("Eksik bilgiler:\n- İşçi yer altı işlerinde çalışıyorsa:");
    });

    it("leaves out the note and the list of a definite answer without gaps", () => {
        const definite = { ...conditionalAnswer, status: "definite" as const, missing_info: [] };
        const plain = answerPlainText(definite, labels);
        expect(plain).not.toContain("Koşullu cevap");
        expect(plain).not.toContain("Eksik bilgiler");
    });
});
