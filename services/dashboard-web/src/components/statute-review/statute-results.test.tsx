import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { listItem, NEXT_STATUTE_ID, STATUTE_ID } from "@/test/statute-fixtures";
import { renderWithIntl } from "@/test/intl";
import { StatuteResults } from "./statute-results";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const params: StatuteQueueParams = { kind: "statute", statute: "4857", band: "medium", page: 1 };
const second = {
    ...listItem,
    extraction_id: NEXT_STATUTE_ID,
    article_no: "Ek 3",
    heading: null,
    version_count: 1,
    gap_count: 0,
};

async function setup(p: StatuteQueueParams = params, items = [listItem, second], total = 2) {
    const element = await StatuteResults({
        params: p,
        list: Promise.resolve({ data: { total, items } }),
    });
    return renderWithIntl(element);
}

describe("StatuteResults", () => {
    it("renders the table and the card list of the same articles, CSS shows one", async () => {
        const { container } = await setup();
        const table = within(screen.getByRole("table"));
        expect(table.getAllByRole("row")).toHaveLength(3);
        const list = screen.getByRole("list", { name: messages.review.statutes.table.label });
        expect(
            within(list)
                .getAllByRole("listitem")
                .filter((li) => li.parentElement === list),
        ).toHaveLength(2);
        expect(container.querySelector(".hidden.xl\\:block table")).not.toBeNull();
        expect(container.querySelector(".xl\\:hidden ul")).not.toBeNull();
    });

    it("reads an article as 'm. 18 · heading', with its versions and gaps", async () => {
        await setup();
        const table = within(screen.getByRole("table"));
        expect(
            table.getByRole("link", { name: "m. 18 · Feshin geçerli sebebe dayandırılması" }),
        ).toBeInTheDocument();
        expect(table.getByText("3 sürüm · 1 boşluk")).toBeInTheDocument();
        // An article without a gap does not say "0 boşluk"; Ek and Geçici articles keep their name.
        expect(table.getByRole("link", { name: "Ek 3" })).toBeInTheDocument();
        expect(table.getByText("1 sürüm")).toBeInTheDocument();
    });

    it("links each article to its detail screen with the queue state and its position", async () => {
        await setup({ ...params, page: 2 }, [listItem], 51);
        const link = within(screen.getByRole("table")).getByRole("link");
        expect(link).toHaveAttribute("href", `/mevzuat/${STATUTE_ID}?band=medium&page=2&pos=50`);
    });

    it("shows the band as a badge and the first reason in short words", async () => {
        await setup();
        const row = screen.getAllByRole("row")[1] as HTMLElement;
        expect(within(row).getByText(messages.enums.band.medium)).toBeInTheDocument();
        expect(
            within(row).getByText(messages.enums.statuteReason.multi_amendment_in_window),
        ).toBeInTheDocument();
        expect(within(row).getByText("+1")).toBeInTheDocument();
    });

    it("adds the status column outside the queue tab", async () => {
        await setup({ ...params, status: "approved" }, [{ ...listItem, status: "approved" }], 1);
        expect(
            within(screen.getByRole("table")).getByText(messages.enums.statuteStatus.approved),
        ).toBeInTheDocument();
    });

    it("says why there is nothing: nothing waits, the filters match nothing, or the page is past the end", async () => {
        const { unmount } = await setup({ ...params, band: undefined }, [], 0);
        expect(screen.getByText(messages.review.statutes.empty.pending)).toBeInTheDocument();
        unmount();
        const filtered = await setup(params, [], 0);
        expect(screen.getByText(messages.review.queue.empty.filtered)).toBeInTheDocument();
        expect(
            screen.getByRole("link", { name: messages.review.queue.filters.clear }),
        ).toHaveAttribute("href", "/mevzuat");
        filtered.unmount();
        await setup({ ...params, page: 9 }, [], 3);
        expect(screen.getByText(messages.review.queue.empty.pastEnd)).toBeInTheDocument();
    });

    it("shows the translated message of an API refusal", async () => {
        const element = await StatuteResults({
            params,
            list: Promise.resolve({ error: { code: "forbidden", params: {} } }),
        });
        renderWithIntl(element);
        expect(screen.getByRole("alert")).toHaveTextContent(messages.errors.forbidden);
    });
});
