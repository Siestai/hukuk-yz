import { act, fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { MAX_JOURNAL_ISSUE } from "@/lib/queue-params";
import { renderWithIntl } from "@/test/intl";
import { QueueFilters } from "./queue-filters";
import { QueueNavigationProvider } from "./queue-navigation";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const { filters } = messages.review.queue;
const courts = ["yargitay", "bam", "", "ufo"];

const view = () => (
    <QueueNavigationProvider>
        <QueueFilters courts={courts} />
    </QueueNavigationProvider>
);

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
        renderWithIntl(view());
        await user.selectOptions(screen.getByLabelText(filters.band), "low");
        expect(nav.push).toHaveBeenCalledWith("/?band=low&sort=score_desc");
    });

    it("writes the court, and the unknown court as `unknown`", async () => {
        const { user } = setup();
        renderWithIntl(view());
        const select = screen.getByLabelText(filters.court);
        await user.selectOptions(select, "bam");
        expect(nav.push).toHaveBeenLastCalledWith("/?court=bam");
        await user.selectOptions(select, messages.enums.court.unknown);
        expect(nav.push).toHaveBeenLastCalledWith("/?court=unknown");
    });

    it("offers the courts of the summary in enum order and ignores courts it does not know", () => {
        setup();
        renderWithIntl(view());
        const options = [...screen.getByLabelText<HTMLSelectElement>(filters.court).options].map(
            (o) => o.textContent,
        );
        expect(options).toEqual([
            filters.allCourts,
            messages.enums.court.yargitay,
            messages.enums.court.bam,
            messages.enums.court.unknown,
        ]);
    });

    it("keeps a court from the URL selectable even when the summary has none", () => {
        setup("court=aym");
        renderWithIntl(
            <QueueNavigationProvider>
                <QueueFilters courts={["yargitay"]} />
            </QueueNavigationProvider>,
        );
        expect(screen.getByLabelText(filters.court)).toHaveValue("aym");
    });

    it("lists every reason with its label and writes the chosen one", async () => {
        const { user } = setup();
        renderWithIntl(view());
        const select = screen.getByLabelText<HTMLSelectElement>(filters.reason);
        expect(select.options).toHaveLength(Object.keys(messages.enums.reason).length + 1);
        await user.selectOptions(select, messages.enums.reason.duplicate_of);
        expect(nav.push).toHaveBeenCalledWith("/?reason=duplicate_of");
    });

    it("clears a filter when the empty option is chosen", async () => {
        const { user } = setup("band=low&page=3");
        renderWithIntl(view());
        await user.selectOptions(screen.getByLabelText(filters.band), filters.allBands);
        expect(nav.push).toHaveBeenCalledWith("/");
    });

    it("writes the journal issue on Enter and on blur", async () => {
        const { user } = setup();
        renderWithIntl(view());
        const input = screen.getByLabelText(filters.journalIssue);
        await user.type(input, "77{Enter}");
        expect(nav.push).toHaveBeenCalledWith("/?journal_issue=77");
        nav.push.mockClear();
        await user.clear(input);
        await user.type(input, "8");
        await user.tab();
        expect(nav.push).toHaveBeenCalledWith("/?journal_issue=8");
    });

    it("builds a second quick change on the first one", () => {
        setup();
        renderWithIntl(view());
        const band = screen.getByLabelText(filters.band);
        const court = screen.getByLabelText(filters.court);
        act(() => {
            fireEvent.change(band, { target: { value: "low" } });
            fireEvent.change(court, { target: { value: "bam" } });
        });
        expect(nav.push).toHaveBeenNthCalledWith(1, "/?band=low");
        expect(nav.push).toHaveBeenNthCalledWith(2, "/?band=low&court=bam");
    });

    it("limits the journal issue input to the range the URL accepts", () => {
        setup();
        renderWithIntl(view());
        expect(screen.getByLabelText(filters.journalIssue)).toHaveAttribute(
            "max",
            String(MAX_JOURNAL_ISSUE),
        );
    });

    it("pushes the journal issue once when Enter is followed by blur", async () => {
        const { user } = setup();
        renderWithIntl(view());
        await user.type(screen.getByLabelText(filters.journalIssue), "77{Enter}");
        await user.tab();
        expect(nav.push).toHaveBeenCalledTimes(1);
    });

    it("ignores a journal issue that is not a whole number in range", async () => {
        const { user } = setup();
        renderWithIntl(view());
        const input = screen.getByLabelText(filters.journalIssue);
        await user.type(input, "1.5{Enter}");
        await user.clear(input);
        await user.type(input, "99999999{Enter}");
        expect(nav.push).not.toHaveBeenCalled();
    });

    it("clears the journal issue when the input is emptied", async () => {
        const { user } = setup("journal_issue=5");
        renderWithIntl(view());
        const input = screen.getByLabelText(filters.journalIssue);
        await user.clear(input);
        await user.type(input, "{Enter}");
        expect(nav.push).toHaveBeenCalledWith("/");
    });

    it("does not navigate when the journal issue is unchanged", async () => {
        const { user } = setup("journal_issue=5");
        renderWithIntl(view());
        const input = screen.getByLabelText(filters.journalIssue);
        await user.click(input);
        await user.tab();
        expect(nav.push).not.toHaveBeenCalled();
    });

    describe("search", () => {
        it("replaces the URL after the 300 ms pause following the last keystroke", async () => {
            const { user } = setup("page=2");
            renderWithIntl(view());
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
            renderWithIntl(view());
            await user.type(screen.getByLabelText(filters.search), "2019/12{Enter}");
            expect(nav.push).toHaveBeenCalledWith("/?q=2019%2F12");
            act(() => vi.advanceTimersByTime(1000));
            expect(nav.replace).not.toHaveBeenCalled();
        });

        it("starts with the text of the URL and does not write it back", () => {
            setup("q=kıdem");
            renderWithIntl(view());
            expect(screen.getByLabelText(filters.search)).toHaveValue("kıdem");
            act(() => vi.advanceTimersByTime(1000));
            expect(nav.replace).not.toHaveBeenCalled();
        });
    });

    describe("clear link", () => {
        it("is absent without filters, even with a sort and page", () => {
            setup("sort=score_desc&page=2");
            renderWithIntl(view());
            expect(screen.queryByRole("link", { name: filters.clear })).toBeNull();
        });

        it("clears the filters but keeps the sort", () => {
            setup("band=low&q=x&sort=score_desc&page=2");
            renderWithIntl(view());
            expect(screen.getByRole("link", { name: filters.clear })).toHaveAttribute(
                "href",
                "/?sort=score_desc",
            );
        });
    });

    describe("phone toggle", () => {
        const toggle = () => screen.getByRole("button", { name: new RegExp(filters.toggle) });

        it("is closed without filters and opens and closes the fields", async () => {
            const { user } = setup();
            renderWithIntl(view());
            expect(toggle()).toHaveTextContent(filters.toggle);
            expect(toggle()).toHaveAttribute("aria-expanded", "false");
            const body = document.getElementById(toggle().getAttribute("aria-controls") ?? "");
            expect(body).toContainElement(screen.getByLabelText(filters.band));
            expect(body).toHaveClass("hidden", "md:flex");
            await user.click(toggle());
            expect(toggle()).toHaveAttribute("aria-expanded", "true");
            expect(body).toHaveClass("grid");
            expect(body).not.toHaveClass("hidden");
            await user.click(toggle());
            expect(body).toHaveClass("hidden");
        });

        it("starts open and counts the active filters when a filter is set", () => {
            setup("band=low&q=x");
            renderWithIntl(view());
            expect(toggle()).toHaveTextContent("Filtreler (2)");
            expect(toggle()).toHaveAttribute("aria-expanded", "true");
        });

        it("is hidden from md up, where the fields are always shown", () => {
            setup();
            renderWithIntl(view());
            expect(toggle()).toHaveClass("md:hidden");
        });

        it("gives the fields the full width on a phone and fixed widths from md up", () => {
            setup();
            renderWithIntl(view());
            const field = screen.getByLabelText(filters.band).parentElement;
            expect(field).toHaveClass("md:w-40");
            expect(field).not.toHaveClass("w-40");
        });
    });
});
