import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { QueueNavigationProvider } from "@/components/review-queue/queue-navigation";
import { renderWithIntl } from "@/test/intl";
import { StatuteFilters } from "./statute-filters";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const { filters } = messages.review.queue;

function setup(search = "") {
    nav.search = search;
    renderWithIntl(
        <QueueNavigationProvider kind="statute">
            <StatuteFilters />
        </QueueNavigationProvider>,
    );
    return userEvent.setup();
}

beforeEach(() => {
    nav.push.mockClear();
    nav.replace.mockClear();
});

describe("StatuteFilters", () => {
    it("writes the band to the URL of the statute queue, keeping the statute and resetting the page", async () => {
        const user = setup("kanun=5510&page=4");
        await user.selectOptions(screen.getByLabelText(filters.band), "low");
        expect(nav.push).toHaveBeenCalledWith("/mevzuat?kanun=5510&band=low");
    });

    it("writes a search on Enter", async () => {
        const user = setup();
        await user.type(screen.getByRole("searchbox"), "fesih{Enter}");
        expect(nav.push).toHaveBeenCalledWith("/mevzuat?q=fesih");
    });

    it("clears the filters but keeps the statute and the tab", () => {
        setup("durum=onaylanan&kanun=5510&band=high&q=x");
        expect(screen.getByRole("link", { name: filters.clear })).toHaveAttribute(
            "href",
            "/mevzuat?durum=onaylanan&kanun=5510",
        );
        expect(screen.getByRole("button", { name: /Filtreler \(2\)/ })).toBeInTheDocument();
    });

    it("offers no clear link without filters", () => {
        setup("kanun=5510");
        expect(screen.queryByRole("link", { name: filters.clear })).not.toBeInTheDocument();
    });
});
