import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { parseQueueParams } from "@/lib/queue-params";
import { BandDistribution, bandSegments } from "./band-distribution";

const counts = { high: 5906, medium: 101, low: 310 };

const view = (search = "") => (
    <BandDistribution counts={counts} params={parseQueueParams(new URLSearchParams(search))} />
);

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
        renderWithIntl(view());
        expect(screen.getByRole("img")).toHaveAccessibleName(
            "Bekleyen kararların güven dağılımı: Yüksek 5.906, Orta 101, Düşük 310",
        );
    });

    it("shows a legend link with the count of every band", () => {
        renderWithIntl(view());
        expect(screen.getByRole("link", { name: /Yüksek/ })).toHaveTextContent("5.906");
        expect(screen.getByRole("link", { name: /Orta/ })).toHaveTextContent("101");
        expect(screen.getByRole("link", { name: /Düşük/ })).toHaveTextContent("310");
    });

    it("links to the band filter on page 1, keeping the other state", () => {
        renderWithIntl(view("page=3&sort=score_desc"));
        expect(screen.getByRole("link", { name: /Düşük/ })).toHaveAttribute(
            "href",
            "/?band=low&sort=score_desc",
        );
    });

    it("marks the active band and links it to its own removal", () => {
        renderWithIntl(view("band=medium&sort=score_desc"));
        const link = screen.getByRole("link", { name: new RegExp(messages.enums.band.medium) });
        expect(link).toHaveAttribute("aria-current", "true");
        expect(link).toHaveAttribute("href", "/?sort=score_desc");
        expect(screen.getByRole("link", { name: /Düşük/ })).not.toHaveAttribute("aria-current");
    });
});
