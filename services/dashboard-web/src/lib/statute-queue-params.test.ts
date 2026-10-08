import { describe, expect, it } from "vitest";

import {
    activeStatuteFilterCount,
    changeStatuteParams,
    parseStatuteParams,
    serializeStatuteParams,
    statuteApiQuery,
    statuteDetailHref,
    statuteListHref,
    statuteTabParams,
    type StatuteQueueParams,
} from "./statute-queue-params";

const base: StatuteQueueParams = { kind: "statute", statute: "4857", page: 1 };

describe("parseStatuteParams", () => {
    it("defaults to the 4857 queue", () => {
        expect(parseStatuteParams(new URLSearchParams())).toEqual({
            kind: "statute",
            band: undefined,
            statute: "4857",
            q: undefined,
            page: 1,
        });
    });

    it("reads the Turkish and shared params of the URL", () => {
        const params = parseStatuteParams(
            new URLSearchParams("kanun=5510&durum=onaylanan&band=low&q=%20fesih%20&page=3"),
        );
        expect(params).toMatchObject({
            statute: "5510",
            status: "approved",
            band: "low",
            q: "fesih",
            page: 3,
        });
    });

    it("ignores what it does not know", () => {
        expect(
            parseStatuteParams({ kanun: "9999", durum: "x", band: "ultra", page: "-1" }),
        ).toEqual({ kind: "statute", statute: "4857", band: undefined, q: undefined, page: 1 });
    });
});

describe("serializeStatuteParams and the hrefs", () => {
    it("leaves the defaults out and round-trips the rest", () => {
        expect(statuteListHref(base)).toBe("/mevzuat");
        const full: StatuteQueueParams = {
            ...base,
            statute: "5510",
            status: "rejected",
            band: "high",
            q: "ücret",
            page: 2,
        };
        expect(serializeStatuteParams(full).toString()).toBe(
            "durum=reddedilen&kanun=5510&band=high&q=%C3%BCcret&page=2",
        );
        expect(parseStatuteParams(serializeStatuteParams(full))).toEqual(full);
    });

    it("carries the queue state, the position and the flash to the detail screen", () => {
        expect(
            statuteDetailHref("e1", { ...base, band: "low" }, { pos: 4, flash: "approved" }),
        ).toBe("/mevzuat/e1?band=low&pos=4&flash=approved");
        expect(statuteDetailHref("e1", base)).toBe("/mevzuat/e1");
    });

    it("puts the notice on the list", () => {
        expect(statuteListHref(base, { flash: "rejected", done: true })).toBe(
            "/mevzuat?flash=rejected&done=1",
        );
    });
});

describe("changing the state", () => {
    it("goes back to the first page unless a page is named", () => {
        const at: StatuteQueueParams = { ...base, page: 4 };
        expect(changeStatuteParams(at, { band: "high" })).toMatchObject({ band: "high", page: 1 });
        expect(changeStatuteParams(at, { page: 5 }).page).toBe(5);
    });

    it("keeps the filters on a tab and opens its first page", () => {
        expect(statuteTabParams({ ...base, band: "low", page: 3 }, "approved")).toMatchObject({
            status: "approved",
            band: "low",
            page: 1,
        });
        expect(statuteTabParams({ ...base, status: "approved" }, "pending").status).toBeUndefined();
    });

    it("counts band and search as the filters", () => {
        expect(activeStatuteFilterCount(base)).toBe(0);
        expect(activeStatuteFilterCount({ ...base, band: "low", q: "x" })).toBe(2);
    });
});

describe("statuteApiQuery", () => {
    it("names the statute and pages by the shared page size", () => {
        expect(statuteApiQuery({ ...base, statute: "5510", band: "high", page: 3 })).toEqual({
            status: undefined,
            band: "high",
            statute: "5510",
            q: undefined,
            limit: 50,
            offset: 100,
        });
    });
});
