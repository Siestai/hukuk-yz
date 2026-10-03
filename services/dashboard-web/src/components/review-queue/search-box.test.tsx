import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";
import { QueueNavigationProvider } from "./queue-navigation";
import { SearchBox } from "./search-box";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const view = () => (
    <QueueNavigationProvider>
        <SearchBox id="q" />
    </QueueNavigationProvider>
);

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    nav.search = "";
    nav.replace.mockClear();
});
afterEach(() => vi.useRealTimers());

describe("SearchBox", () => {
    it("keeps newer typing when the URL answers an older value", async () => {
        const user = userEvent.setup({ delay: null });
        const { rerender } = renderWithIntl(view());
        const input = screen.getByRole("searchbox");
        await user.type(input, "ab");
        act(() => vi.advanceTimersByTime(400));
        expect(nav.replace).toHaveBeenLastCalledWith("/?q=ab");
        await user.type(input, "c");
        act(() => vi.advanceTimersByTime(400));
        expect(nav.replace).toHaveBeenLastCalledWith("/?q=abc");

        nav.search = "q=ab";
        rerender(view());
        expect(input).toHaveValue("abc");

        nav.search = "q=abc";
        rerender(view());
        expect(input).toHaveValue("abc");
    });

    it("takes over a URL value it did not send, such as clearing the filters", async () => {
        const user = userEvent.setup({ delay: null });
        const { rerender } = renderWithIntl(view());
        const input = screen.getByRole("searchbox");
        await user.type(input, "ab");
        act(() => vi.advanceTimersByTime(400));
        nav.search = "q=ab";
        rerender(view());

        nav.search = "";
        rerender(view());
        expect(input).toHaveValue("");
        act(() => vi.advanceTimersByTime(1000));
        expect(nav.replace).toHaveBeenCalledTimes(1);
    });
});
