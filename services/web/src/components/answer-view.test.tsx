import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { conditionalAnswer, sourceGap } from "@/test/answer-fixture";
import { renderWithIntl } from "@/test/intl";
import { AnswerView, SourceGapNote } from "./answer-view";

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
        expect(screen.getByText(/İşçi yer altı işlerinde çalışmaktaysa/)).toBeVisible();
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

    it("shows no missing-info section for a source-gap answer without user-completable facts", () => {
        renderWithIntl(
            <AnswerView
                answer={{ ...conditionalAnswer, missing_info: [], source_gap: sourceGap }}
                mode="short"
                facts={null}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.queryByText("Tamamlanması gereken bilgiler")).not.toBeInTheDocument();
    });

    it("draws no holding table for a source-gap answer with no verified row", () => {
        renderWithIntl(
            <AnswerView
                answer={{
                    ...conditionalAnswer,
                    source_gap: sourceGap,
                    holding_map: { ...conditionalAnswer.holding_map, rows: [] },
                }}
                mode="reasoned"
                facts={null}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.queryByText("Koşullar olaya uyuyor mu?")).not.toBeInTheDocument();
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

describe("SourceGapNote", () => {
    it("lists the topic, the unread sources with their reason, the given facts and the next step", () => {
        renderWithIntl(<SourceGapNote gap={sourceGap} />);
        const lines = screen.getAllByRole("listitem").map((item) => item.textContent);
        expect(lines).toEqual([
            "Konu: İşe iade",
            "Okunamayan kaynaklar: 4857 m.18 (bilgi tabanında yok) ve 7036 m.3 (olay tarihinde yürürlükte değil)",
            "Verdiğiniz bilgiler: Kıdem: 5 ay",
            sourceGap.next_step,
        ]);
    });

    it("is part of a fallback answer", () => {
        renderWithIntl(
            <AnswerView
                answer={{ ...conditionalAnswer, source_gap: sourceGap }}
                mode="short"
                facts={null}
                onOpenCitation={vi.fn()}
            />,
        );
        expect(screen.getByText(sourceGap.next_step)).toBeInTheDocument();
    });
});
