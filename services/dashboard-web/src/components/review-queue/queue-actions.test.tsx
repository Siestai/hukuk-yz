import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, renderWithIntl } from "@/test/intl";
import { QueueActions } from "./queue-actions";
import { QueueNavigationProvider } from "./queue-navigation";

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams(),
}));

describe("QueueActions", () => {
    it("has the sort select with a tip beside it", () => {
        renderWithIntl(
            <QueueNavigationProvider>
                <QueueActions />
            </QueueNavigationProvider>,
        );
        expect(
            screen.getByRole("combobox", { name: messages.review.queue.sort.label }),
        ).toBeInTheDocument();
        expect(infoTip(messages.review.queue.sort.label)).toBeInTheDocument();
    });
});
