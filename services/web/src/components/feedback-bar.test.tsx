import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { postFeedback } from "@/lib/chat-client";
import { renderWithIntl } from "@/test/intl";
import { conditionalAnswer } from "@/test/answer-fixture";
import { FeedbackBar } from "./feedback-bar";

vi.mock("@/lib/chat-client", () => ({ postFeedback: vi.fn() }));

beforeEach(() => vi.mocked(postFeedback).mockReset());

describe("FeedbackBar", () => {
    it("posts a thumbs-up once and then locks the buttons", async () => {
        let finish: () => void = () => undefined;
        vi.mocked(postFeedback).mockReturnValue(
            new Promise((resolve) => (finish = () => resolve({} as never))),
        );
        renderWithIntl(<FeedbackBar turnId="t1" answer={conditionalAnswer} />);
        const up = screen.getByRole("button", { name: "Faydalı" });
        await userEvent.click(up);
        await userEvent.click(up);
        expect(up).toBeDisabled();
        finish();

        expect(await screen.findByText("Geri bildiriminiz alındı: faydalı.")).toBeInTheDocument();
        expect(postFeedback).toHaveBeenCalledExactlyOnceWith(expect.anything(), "t1", {
            rating: "up",
            comment: "",
            correction: "",
        });
        expect(up).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByRole("button", { name: "Hatalı" })).toBeDisabled();
    });

    it("shows the error of a failed post and allows another try", async () => {
        vi.mocked(postFeedback).mockRejectedValueOnce(new ApiFailure("upstream_unavailable"));
        renderWithIntl(<FeedbackBar turnId="t1" answer={conditionalAnswer} />);
        await userEvent.click(screen.getByRole("button", { name: "Faydalı" }));
        await waitFor(() => expect(screen.getByRole("alert")).not.toBeEmptyDOMElement());
        expect(screen.getByRole("button", { name: "Faydalı" })).toBeEnabled();
    });

    it("copies the answer, then goes back to Kopyala", async () => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        try {
            const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
            const write = vi.spyOn(navigator.clipboard, "writeText");
            renderWithIntl(<FeedbackBar turnId="t1" answer={conditionalAnswer} />);
            await user.click(screen.getByRole("button", { name: "Kopyala" }));
            expect(write).toHaveBeenCalledOnce();
            expect(write.mock.calls[0]?.[0]).toContain(conditionalAnswer.headline);
            expect(screen.getByRole("button", { name: "Kopyalandı" })).toBeInTheDocument();
            await act(() => vi.advanceTimersByTimeAsync(2500));
            expect(screen.getByRole("button", { name: "Kopyala" })).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it("tells the user when the clipboard refuses", async () => {
        const user = userEvent.setup();
        vi.spyOn(navigator.clipboard, "writeText").mockRejectedValue(new Error("denied"));
        renderWithIntl(<FeedbackBar turnId="t1" answer={conditionalAnswer} />);
        await user.click(screen.getByRole("button", { name: "Kopyala" }));
        expect(await screen.findByText(/Kopyalanamadı/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Kopyala" })).toBeInTheDocument();
    });
});
