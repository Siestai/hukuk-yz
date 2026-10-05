import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, renderWithIntl } from "@/test/intl";
import { QueueActions } from "./queue-actions";
import { QueueNavigationProvider } from "./queue-navigation";

const search = vi.hoisted(() => ({ query: "" }));
vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams(search.query),
}));

function sortOptions() {
    renderWithIntl(
        <QueueNavigationProvider>
            <QueueActions />
        </QueueNavigationProvider>,
    );
    const select = screen.getByRole("combobox", { name: messages.review.queue.sort.label });
    return {
        select,
        labels: within(select)
            .getAllByRole("option")
            .map((option) => option.textContent),
    };
}

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

    it("offers no sort by review in the queue, where nothing was reviewed", () => {
        search.query = "";
        const { labels } = sortOptions();
        expect(labels).toEqual([
            messages.review.queue.sort.score_asc,
            messages.review.queue.sort.score_desc,
        ]);
    });

    it("offers the newest review first in the other tabs and selects it where it is the default", () => {
        search.query = "durum=reddedilen";
        const { select, labels } = sortOptions();
        expect(labels).toContain(messages.review.queue.sort.reviewed_desc);
        expect(select).toHaveValue("reviewed_desc");
    });

    it("keeps the score sort as the default of the all tab", () => {
        search.query = "durum=tumu";
        const { select, labels } = sortOptions();
        expect(labels).toHaveLength(3);
        expect(select).toHaveValue("score_asc");
    });
});
