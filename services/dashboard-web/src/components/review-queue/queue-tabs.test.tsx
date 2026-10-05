import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import type { QueueParams } from "@/lib/queue-params";
import { infoTip, renderWithIntl } from "@/test/intl";
import { QueueTabs } from "./queue-tabs";

const { tabs, help } = messages.review.queue;
const counts = { pending: 12, approved: 1200, rejected: 3, all: 1215 };

function setup(params: QueueParams) {
    renderWithIntl(<QueueTabs params={params} counts={counts} />);
    return screen.getByRole("navigation", { name: tabs.label });
}

describe("QueueTabs", () => {
    it("is a navigation with the four tabs and their counts", () => {
        const nav = setup({ sort: "score_asc", page: 1 });
        const links = within(nav).getAllByRole("link");
        expect(links.map((link) => link.textContent)).toEqual([
            `${tabs.pending}12`,
            `${tabs.approved}1.200`,
            `${tabs.rejected}3`,
            `${tabs.all}1.215`,
        ]);
    });

    it("marks the open tab with aria-current and no other", () => {
        const nav = setup({ status: "rejected", sort: "reviewed_desc", page: 1 });
        const current = within(nav).getAllByRole("link", { current: "page" });
        expect(current).toHaveLength(1);
        expect(current[0]).toHaveTextContent(tabs.rejected);
    });

    it("marks the queue when no tab is named", () => {
        const nav = setup({ sort: "score_asc", page: 1 });
        expect(within(nav).getByRole("link", { current: "page" })).toHaveTextContent(tabs.pending);
    });

    it("links each tab to its URL, keeping the filters and starting at page 1", () => {
        const nav = setup({ band: "low", sort: "score_desc", page: 3 });
        const href = (name: string) =>
            within(nav)
                .getByRole("link", { name: new RegExp(`^${name}`) })
                .getAttribute("href");
        expect(href(tabs.pending)).toBe("/?band=low");
        expect(href(tabs.approved)).toBe("/?durum=onaylanan&band=low");
        expect(href(tabs.rejected)).toBe("/?durum=reddedilen&band=low");
        expect(href(tabs.all)).toBe("/?durum=tumu&band=low");
    });

    it("explains every tab with a tip beside its link", () => {
        setup({ sort: "score_asc", page: 1 });
        for (const [name, text] of [
            [tabs.pending, help.tabPending],
            [tabs.approved, help.tabApproved],
            [tabs.rejected, help.tabRejected],
            [tabs.all, help.tabAll],
        ] as const) {
            expect(infoTip(name)).toBeInTheDocument();
            expect(text.length).toBeGreaterThan(0);
        }
    });
});
