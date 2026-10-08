import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { QueueParams } from "@/lib/queue-params";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import type { QueueState } from "@/lib/queue-state";
import { infoTip, renderWithIntl } from "@/test/intl";
import { BulkApproveButton } from "./bulk-approve-button";
import { QueueNavigationProvider } from "./queue-navigation";

const nav = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(),
}));

const { bulk } = messages.review;
const queue = (band?: QueueParams["band"]): QueueParams => ({ band, sort: "score_asc", page: 1 });

function setup(params: QueueState, extra: { unavailable?: boolean } = {}) {
    renderWithIntl(
        <QueueNavigationProvider>
            <BulkApproveButton params={params} total={12} sample={[]} {...extra} />
        </QueueNavigationProvider>,
    );
}

describe("BulkApproveButton", () => {
    it("is enabled on the high band and opens the dialog with the count of the list", async () => {
        setup(queue("high"));
        await userEvent.click(screen.getByRole("button", { name: bulk.open }));
        expect(screen.getByRole("dialog", { name: bulk.title })).toBeInTheDocument();
        expect(screen.getByText("12 karar")).toBeInTheDocument();
    });

    it.each([undefined, "medium", "low"] as const)(
        "stays disabled and says why when the band is %s",
        (band) => {
            setup(queue(band));
            const button = screen.getByRole("button", { name: bulk.open });
            expect(button).toBeDisabled();
            expect(button).toHaveAccessibleDescription(bulk.bandOnly);
            expect(button.parentElement).toHaveAttribute("title", bulk.bandOnly);
        },
    );

    it("is shut while there is no list to confirm", () => {
        setup(queue("high"), { unavailable: true });
        expect(screen.getByRole("button", { name: bulk.open })).toBeDisabled();
    });
});

describe("BulkApproveButton on the statute queue", () => {
    const statutes = (q?: string): StatuteQueueParams => ({
        kind: "statute",
        statute: "4857",
        band: "high",
        q,
        page: 1,
    });

    it("is enabled on the high band without a search", () => {
        setup(statutes());
        expect(screen.getByRole("button", { name: bulk.open })).toBeEnabled();
    });

    it("is disabled under a search, says why, and never opens a dialog", async () => {
        setup(statutes("fesih"));
        const button = screen.getByRole("button", { name: bulk.open });
        expect(button).toBeDisabled();
        expect(button).toHaveAccessibleDescription(bulk.searchOnly);
        expect(button.parentElement).toHaveAttribute("title", bulk.searchOnly);
        await userEvent.click(button);
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("keeps the decision queue's search from disabling the button", () => {
        setup({ ...queue("high"), q: "işçi" });
        expect(screen.getByRole("button", { name: bulk.open })).toBeEnabled();
    });
});

describe("BulkApproveButton help", () => {
    it("has a tip beside the button, also while the button is disabled", () => {
        setup(queue());
        expect(screen.getByRole("button", { name: bulk.open })).toBeDisabled();
        expect(infoTip(bulk.open)).toBeEnabled();
    });
});
