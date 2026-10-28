import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { conditionalAnswer } from "@/test/answer-fixture";
import { renderWithIntl } from "@/test/intl";
import { AnswerView } from "./answer-view";

function setup(mode: "short" | "detailed" | "reasoned") {
    const onOpenCitation = vi.fn();
    renderWithIntl(
        <AnswerView
            answer={conditionalAnswer}
            mode={mode}
            facts={null}
            onOpenCitation={onOpenCitation}
        />,
    );
    return onOpenCitation;
}

describe("AnswerView", () => {
    it("opens the missing information of a conditional answer by default", () => {
        setup("short");
        expect(screen.getByText("Koşullu cevap")).toBeInTheDocument();
        expect(screen.getByText("Tamamlanması gereken bilgiler")).toBeInTheDocument();
        expect(screen.getByText(/İşçi yer altı işlerinde çalışıyorsa/)).toBeVisible();
    });

    it("shows the first points in short mode and all of them in detailed mode", () => {
        const { points, short_point_count: shortCount } = conditionalAnswer;
        expect(points.length).toBeGreaterThan(shortCount);
        const { unmount } = renderWithIntl(
            <AnswerView
                answer={conditionalAnswer}
                mode="short"
                facts={null}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.queryByText(points[shortCount]!.text)).not.toBeInTheDocument();
        expect(screen.getByText(points[0]!.text)).toBeInTheDocument();
        unmount();
        renderWithIntl(
            <AnswerView
                answer={conditionalAnswer}
                mode="detailed"
                facts={null}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.getByText(points[shortCount]!.text)).toBeInTheDocument();
    });

    it("replaces the points with the holding table in reasoned mode", () => {
        setup("reasoned");
        expect(screen.queryByText(conditionalAnswer.points[0]!.text)).not.toBeInTheDocument();
        expect(
            screen.getByText(conditionalAnswer.holding_map.reasoning_summary),
        ).toBeInTheDocument();
    });

    it("hands the tapped source to the viewer", async () => {
        const onOpen = setup("detailed");
        const first = conditionalAnswer.points[0]!.citations[0]!;
        const [link] = screen.getAllByRole("button", { name: `Dayanağı aç: ${first.label}` });
        await userEvent.click(link!);
        expect(onOpen).toHaveBeenCalledWith(
            expect.objectContaining({ source_id: first.source_id }),
        );
    });

    it("ends with the applied law and the disclaimer", () => {
        setup("short");
        const footer = screen.getByText("Hukuki görüş değildir.").closest("footer")!;
        expect(within(footer).getByText("Uygulanan mevzuat:")).toBeInTheDocument();
    });
});
