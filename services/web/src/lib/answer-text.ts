import type { Answer } from "./chat-types";

export type AnswerTextLabels = {
    /** "Dayanak", before the sources of a point. */
    basis: string;
    /** "Koşullu cevap", before the note of a conditional answer. */
    conditional: string;
    /** "Tamamlanması gereken bilgiler". */
    missing: string;
};

/** The answer as plain text for a chat message: headline, points with their sources, the disclaimer. */
export function answerPlainText(answer: Answer, labels: AnswerTextLabels): string {
    const lines = [answer.headline, ""];
    if (answer.status === "conditional")
        lines.push(`${labels.conditional}: ${answer.status_note}`, "");
    for (const point of answer.points) {
        lines.push(`- ${point.text}`);
        if (point.citations.length > 0) {
            lines.push(`  ${labels.basis}: ${point.citations.map((c) => c.label).join(", ")}`);
        }
    }
    if (answer.missing_info.length > 0) {
        lines.push("", `${labels.missing}:`);
        for (const info of answer.missing_info) lines.push(`- ${info.condition}: ${info.result}`);
    }
    lines.push("", answer.disclaimer);
    return lines.join("\n");
}
