import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { TopReasons } from "./top-reasons";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const reasons = Object.keys(messages.enums.reason)
    .slice(0, 7)
    .map((reason, i) => ({ reason, count: 2000 - i }));

beforeEach(() => {
    nav.search = "";
    nav.push.mockClear();
});

describe("TopReasons", () => {
    it("lists the first five reasons with labels and counts", () => {
        renderWithIntl(<TopReasons reasons={reasons} />);
        const buttons = screen.getAllByRole("button");
        expect(buttons).toHaveLength(5);
        expect(buttons[0]).toHaveTextContent(`${messages.enums.reason.missing_court}2.000`);
    });

    it("sets the reason filter", async () => {
        renderWithIntl(<TopReasons reasons={reasons} />);
        await userEvent.setup().click(screen.getByRole("button", { name: /Esas no yok/ }));
        expect(nav.push).toHaveBeenCalledWith("/?reason=missing_esas_no");
    });

    it("says so when there are no reasons", () => {
        renderWithIntl(<TopReasons reasons={[]} />);
        expect(screen.getByText(messages.review.queue.summary.noReasons)).toBeInTheDocument();
    });
});
