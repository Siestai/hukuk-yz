import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { postFeedback } from "@/lib/chat-client";
import { conditionalAnswer } from "@/test/answer-fixture";
import { renderWithIntl } from "@/test/intl";
import { FeedbackDialog } from "./feedback-dialog";

vi.mock("@/lib/chat-client", () => ({ postFeedback: vi.fn() }));
beforeEach(() => vi.mocked(postFeedback).mockReset());

describe("FeedbackDialog", () => {
    it("locks submission until the feedback request finishes", async () => {
        let finish: () => void = () => undefined;
        vi.mocked(postFeedback).mockReturnValue(
            new Promise((resolve) => {
                finish = () => resolve({} as never);
            }),
        );
        const onSent = vi.fn();
        renderWithIntl(
            <FeedbackDialog
                open
                rating="down"
                turnId="t1"
                points={conditionalAnswer.points}
                onClose={vi.fn()}
                onSent={onSent}
            />,
        );
        const submit = screen.getByRole("button", { name: "Gönder" });
        await userEvent.click(submit);
        await userEvent.click(submit);
        expect(submit).toBeDisabled();
        expect(postFeedback).toHaveBeenCalledOnce();
        await act(async () => finish());
        expect(onSent).toHaveBeenCalledOnce();
    });
    it.each(["down", null] as const)(
        "posts the selected point and fields with rating %s",
        async (rating) => {
            vi.mocked(postFeedback).mockResolvedValue({} as never);
            const onSent = vi.fn();
            renderWithIntl(
                <FeedbackDialog
                    open
                    rating={rating}
                    turnId="t1"
                    points={conditionalAnswer.points}
                    onClose={vi.fn()}
                    onSent={onSent}
                />,
            );
            await userEvent.selectOptions(screen.getByLabelText("Hangi madde?"), "0");
            await userEvent.selectOptions(screen.getByLabelText("Hata türü"), "wrong_source");
            await userEvent.type(screen.getByLabelText("Yorum (isteğe bağlı)"), " Yorum ");
            await userEvent.type(screen.getByLabelText("Doğrusu (isteğe bağlı)"), " Düzeltme ");
            await userEvent.click(screen.getByRole("button", { name: "Gönder" }));
            await waitFor(() => expect(onSent).toHaveBeenCalledOnce());
            expect(postFeedback).toHaveBeenCalledExactlyOnceWith(expect.anything(), "t1", {
                rating,
                point_index: 0,
                kind: "wrong_source",
                comment: "Yorum",
                correction: "Düzeltme",
            });
        },
    );
});
