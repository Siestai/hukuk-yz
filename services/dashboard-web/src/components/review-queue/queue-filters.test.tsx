import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { QueueFilters } from "./queue-filters";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const { filters } = messages.review.queue;
const courts = ["yargitay", "bam", "", "ufo"];

function setup(search = "") {
    nav.search = search;
    return { user: userEvent.setup({ delay: null }) };
}

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    nav.push.mockClear();
    nav.replace.mockClear();
});
afterEach(() => vi.useRealTimers());

describe("QueueFilters", () => {
    it("writes the band to the URL and resets the page", async () => {
        const { user } = setup("page=4&sort=score_desc");
        renderWithIntl(<QueueFilters courts={courts} />);
        await user.selectOptions(screen.getByLabelText(filters.band), "low");
        expect(nav.push).toHaveBeenCalledWith("/?band=low&sort=score_desc");
    });

    it("writes the court, and the unknown court as `unknown`", async () => {
        const { user } = setup();
        renderWithIntl(<QueueFilters courts={courts} />);
        const select = screen.getByLabelText(filters.court);
        await user.selectOptions(select, "bam");
        expect(nav.push).toHaveBeenLastCalledWith("/?court=bam");
        await user.selectOptions(select, messages.enums.court.unknown);
        expect(nav.push).toHaveBeenLastCalledWith("/?court=unknown");
    });

    it("offers the courts of the summary in enum order, then courts it does not know", () => {
        setup();
        renderWithIntl(<QueueFilters courts={courts} />);
        const options = [...screen.getByLabelText<HTMLSelectElement>(filters.court).options].map(
            (o) => o.textContent,
        );
        expect(options).toEqual([
            filters.allCourts,
            messages.enums.court.yargitay,
            messages.enums.court.bam,
            messages.enums.court.unknown,
            "ufo",
        ]);
    });

    it("keeps a court from the URL selectable even when the summary has none", () => {
        setup("court=aym");
        renderWithIntl(<QueueFilters courts={["yargitay"]} />);
        expect(screen.getByLabelText(filters.court)).toHaveValue("aym");
    });

    it("lists every reason with its label and writes the chosen one", async () => {
        const { user } = setup();
        renderWithIntl(<QueueFilters courts={courts} />);
        const select = screen.getByLabelText<HTMLSelectElement>(filters.reason);
        expect(select.options).toHaveLength(Object.keys(messages.enums.reason).length + 1);
        await user.selectOptions(select, messages.enums.reason.duplicate_of);
        expect(nav.push).toHaveBeenCalledWith("/?reason=duplicate_of");
    });

    it("clears a filter when the empty option is chosen", async () => {
        const { user } = setup("band=low&page=3");
        renderWithIntl(<QueueFilters courts={courts} />);
        await user.selectOptions(screen.getByLabelText(filters.band), filters.allBands);
        expect(nav.push).toHaveBeenCalledWith("/");
    });

    it("writes the journal issue on Enter and on blur", async () => {
        const { user } = setup();
        renderWithIntl(<QueueFilters courts={courts} />);
        const input = screen.getByLabelText(filters.journalIssue);
        await user.type(input, "77{Enter}");
        expect(nav.push).toHaveBeenCalledWith("/?journal_issue=77");
        nav.push.mockClear();
        await user.clear(input);
        await user.type(input, "8");
        await user.tab();
        expect(nav.push).toHaveBeenCalledWith("/?journal_issue=8");
    });

    it("does not navigate when the journal issue is unchanged", async () => {
        const { user } = setup("journal_issue=5");
        renderWithIntl(<QueueFilters courts={courts} />);
        const input = screen.getByLabelText(filters.journalIssue);
        await user.click(input);
        await user.tab();
        expect(nav.push).not.toHaveBeenCalled();
    });

    describe("search", () => {
        it("replaces the URL after the 300 ms pause following the last keystroke", async () => {
            const { user } = setup("page=2");
            renderWithIntl(<QueueFilters courts={courts} />);
            await user.type(screen.getByLabelText(filters.search), "2019");
            expect(nav.replace).not.toHaveBeenCalled();
            act(() => vi.advanceTimersByTime(200));
            expect(nav.replace).not.toHaveBeenCalled();
            act(() => vi.advanceTimersByTime(150));
            expect(nav.replace).toHaveBeenCalledTimes(1);
            expect(nav.replace).toHaveBeenCalledWith("/?q=2019");
            expect(nav.push).not.toHaveBeenCalled();
        });

        it("submits at once on Enter, with push, and does not repeat after the pause", async () => {
            const { user } = setup();
            renderWithIntl(<QueueFilters courts={courts} />);
            await user.type(screen.getByLabelText(filters.search), "2019/12{Enter}");
            expect(nav.push).toHaveBeenCalledWith("/?q=2019%2F12");
            act(() => vi.advanceTimersByTime(1000));
            expect(nav.replace).not.toHaveBeenCalled();
        });

        it("starts with the text of the URL and does not write it back", () => {
            setup("q=kıdem");
            renderWithIntl(<QueueFilters courts={courts} />);
            expect(screen.getByLabelText(filters.search)).toHaveValue("kıdem");
            act(() => vi.advanceTimersByTime(1000));
            expect(nav.replace).not.toHaveBeenCalled();
        });
    });

    describe("clear link", () => {
        it("is absent without filters, even with a sort and page", () => {
            setup("sort=score_desc&page=2");
            renderWithIntl(<QueueFilters courts={courts} />);
            expect(screen.queryByRole("link", { name: filters.clear })).toBeNull();
        });

        it("clears the filters but keeps the sort", () => {
            setup("band=low&q=x&sort=score_desc&page=2");
            renderWithIntl(<QueueFilters courts={courts} />);
            expect(screen.getByRole("link", { name: filters.clear })).toHaveAttribute(
                "href",
                "/?sort=score_desc",
            );
        });
    });
});
