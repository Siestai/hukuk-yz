import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { BandDistribution, bandSegments } from "./band-distribution";

const nav = vi.hoisted(() => ({ search: "", push: vi.fn(), replace: vi.fn() }));
vi.mock("next/navigation", () => ({
    useRouter: () => nav,
    useSearchParams: () => new URLSearchParams(nav.search),
}));

const counts = { high: 5906, medium: 101, low: 310 };

beforeEach(() => {
    nav.search = "";
    nav.push.mockClear();
});

describe("bandSegments", () => {
    it("sizes the segments in proportion and lays them end to end", () => {
        const [high, medium, low] = bandSegments({ high: 50, medium: 25, low: 25 });
        expect(high).toEqual({ band: "high", x: 0, width: 50 });
        expect(medium).toEqual({ band: "medium", x: 50, width: 25 });
        expect(low).toEqual({ band: "low", x: 75, width: 25 });
    });

    it("fills the bar exactly", () => {
        const segments = bandSegments(counts);
        const last = segments[2];
        expect(last && last.x + last.width).toBeCloseTo(100);
        expect(segments[0]?.width).toBeCloseTo((5906 / 6317) * 100);
    });

    it("has no segments when nothing is pending", () => {
        expect(bandSegments({ high: 0, medium: 0, low: 0 })).toEqual([]);
    });
});

describe("BandDistribution", () => {
    it("describes the bar for assistive technology", () => {
        renderWithIntl(<BandDistribution counts={counts} />);
        expect(screen.getByRole("img")).toHaveAccessibleName(
            "Bekleyen kararların güven dağılımı: Yüksek 5.906, Orta 101, Düşük 310",
        );
    });

    it("shows a legend button with the count of every band", () => {
        renderWithIntl(<BandDistribution counts={counts} />);
        expect(screen.getByRole("button", { name: /Yüksek/ })).toHaveTextContent("5.906");
        expect(screen.getByRole("button", { name: /Orta/ })).toHaveTextContent("101");
        expect(screen.getByRole("button", { name: /Düşük/ })).toHaveTextContent("310");
    });

    it("sets the band filter and goes back to page 1", async () => {
        nav.search = "page=3";
        renderWithIntl(<BandDistribution counts={counts} />);
        await userEvent.setup().click(screen.getByRole("button", { name: /Düşük/ }));
        expect(nav.push).toHaveBeenCalledWith("/?band=low");
    });

    it("toggles the filter off when its band is clicked again", async () => {
        nav.search = "band=medium&sort=score_desc";
        renderWithIntl(<BandDistribution counts={counts} />);
        const button = screen.getByRole("button", { name: new RegExp(messages.enums.band.medium) });
        expect(button).toHaveAttribute("aria-pressed", "true");
        await userEvent.setup().click(button);
        expect(nav.push).toHaveBeenCalledWith("/?sort=score_desc");
    });
});
