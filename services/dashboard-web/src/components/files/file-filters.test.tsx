import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { FileFilters } from "./file-filters";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const { filters } = messages.files;

function setup(search = "") {
    nav.search = search;
    renderWithIntl(<FileFilters />);
    return userEvent.setup({ delay: null });
}

beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    nav.push.mockClear();
    nav.replace.mockClear();
});
afterEach(() => vi.useRealTimers());

describe("FileFilters", () => {
    it("writes the document type to the URL and starts again from the first page", async () => {
        const user = setup("imlec=abc&durum=done");
        await user.selectOptions(screen.getByLabelText(filters.docType), "karar");
        expect(nav.push).toHaveBeenCalledWith("/dosyalar?tur=karar&durum=done");
    });

    it("offers every document type and scan state by its Turkish name", () => {
        setup();
        const types = screen.getByLabelText(filters.docType);
        expect(types.querySelectorAll("option")).toHaveLength(13);
        expect(
            screen.getByRole("option", { name: "Cumhurbaşkanlığı kararnamesi" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("option", { name: "Görüş" })).toBeInTheDocument();
        expect(screen.getByLabelText(filters.scan).querySelectorAll("option")).toHaveLength(7);
        expect(screen.getByRole("option", { name: "Tamamlandı" })).toBeInTheDocument();
    });

    it("writes the scan state", async () => {
        const user = setup("tur=karar");
        await user.selectOptions(screen.getByLabelText(filters.scan), "failed");
        expect(nav.push).toHaveBeenCalledWith("/dosyalar?tur=karar&durum=failed");
    });

    it("lands two quick changes before the URL has caught up with the first", async () => {
        const user = setup();
        await user.selectOptions(screen.getByLabelText(filters.docType), "karar");
        await user.selectOptions(screen.getByLabelText(filters.scan), "failed");
        expect(nav.push).toHaveBeenLastCalledWith("/dosyalar?tur=karar&durum=failed");
    });

    it("searches after a pause while typing, and at once on Enter", async () => {
        const user = setup();
        await user.type(screen.getByLabelText(filters.search), "2020");
        expect(nav.replace).not.toHaveBeenCalled();
        act(() => vi.advanceTimersByTime(300));
        expect(nav.replace).toHaveBeenCalledWith("/dosyalar?q=2020");
        await user.type(screen.getByLabelText(filters.search), "{Enter}");
        expect(nav.push).toHaveBeenCalledWith("/dosyalar?q=2020");
    });

    it("clears the filters and the search box", async () => {
        const user = setup("tur=karar&q=abc");
        expect(screen.getByLabelText(filters.search)).toHaveValue("abc");
        await user.click(screen.getByRole("button", { name: filters.clear }));
        expect(nav.push).toHaveBeenCalledWith("/dosyalar");
        expect(screen.getByLabelText(filters.search)).toHaveValue("");
    });

    it("has no clear button without a filter", () => {
        setup("imlec=abc");
        expect(screen.queryByRole("button", { name: filters.clear })).toBeNull();
    });
});
