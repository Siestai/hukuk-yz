import { describe, expect, it } from "vitest";

import { statuteAsOf, type TimelineEntry } from "./statute-as-of";

const version = (
    valid_from: string,
    valid_to: string | null,
    change_kind: "original" | "amended" | "repealed" | "added" = "amended",
): TimelineEntry => ({
    kind: "version",
    text: `text from ${valid_from}`,
    heading: null,
    valid_from,
    valid_to,
    change_kind,
    amending_ref: null,
    evidence: {},
    confidence: "high",
    footnotes: [],
    warnings: [],
});
const gap = (from: string | null, to: string): TimelineEntry => ({
    kind: "gap",
    from,
    to,
    reason: "before_earliest_snapshot",
    known_amendments: [],
});

const LATEST = "2026-04-22";

// The shape of 4857 m. 18 and m. 20 in the golden set (packages/ingest/tests/fixtures/statutes).
const m18 = [
    gap("2003-06-10", "2014-09-11"),
    version("2014-09-11", "2018-01-01"),
    version("2018-01-01", null),
];
const m20 = [version("2003-06-10", "2018-01-01", "original"), version("2018-01-01", null)];

describe("statuteAsOf", () => {
    it("finds the version in force (golden: m. 20 on 2017-06-01 and 2019-01-01)", () => {
        expect(statuteAsOf(m20, "2017-06-01", LATEST)).toEqual({
            status: "found",
            index: 0,
            stale: false,
        });
        expect(statuteAsOf(m20, "2019-01-01", LATEST)).toMatchObject({ status: "found", index: 1 });
    });

    it("hands a boundary day to the later version: intervals are half open", () => {
        expect(statuteAsOf(m20, "2017-12-31", LATEST)).toMatchObject({ index: 0 });
        expect(statuteAsOf(m20, "2018-01-01", LATEST)).toMatchObject({ index: 1 });
    });

    it("includes the first day of a version", () => {
        expect(statuteAsOf(m20, "2003-06-10", LATEST)).toMatchObject({
            status: "found",
            index: 0,
        });
    });

    it("answers gap where only the amendments are known (golden: m. 18 on 2014-01-01)", () => {
        expect(statuteAsOf(m18, "2014-01-01", LATEST)).toEqual({
            status: "gap",
            index: 0,
            stale: false,
        });
        expect(statuteAsOf(m18, "2014-09-10", LATEST)).toMatchObject({ status: "gap" });
        expect(statuteAsOf(m18, "2014-09-11", LATEST)).toMatchObject({ status: "found", index: 1 });
    });

    it("lets a gap without a start reach back to the beginning of time", () => {
        const open = [gap(null, "2011-02-25"), version("2011-02-25", null)];
        expect(statuteAsOf(open, "1900-01-01", LATEST)).toMatchObject({ status: "gap", index: 0 });
    });

    it("is not in force before the article existed (golden: m. 17 on 2003-03-01)", () => {
        expect(statuteAsOf(m18, "2003-03-01", LATEST)).toEqual({
            status: "not_in_force",
            reason: null,
            index: null,
            stale: false,
        });
        expect(
            statuteAsOf([version("2017-10-25", null, "added")], "2016-01-01", LATEST),
        ).toMatchObject({ status: "not_in_force", reason: null });
    });

    it("is not in force once a version repeals the article, and names the repeal", () => {
        const repealed = [
            version("2003-06-10", "2015-01-01", "original"),
            version("2015-01-01", null, "repealed"),
        ];
        expect(statuteAsOf(repealed, "2016-01-01", LATEST)).toEqual({
            status: "not_in_force",
            reason: "repealed",
            index: 1,
            stale: false,
        });
        expect(statuteAsOf(repealed, "2014-12-31", LATEST)).toMatchObject({ status: "found" });
    });

    it("is not in force after a version that ends without a successor", () => {
        const removed = [version("2003-06-10", "2020-01-01", "original")];
        expect(statuteAsOf(removed, "2020-01-01", LATEST)).toMatchObject({
            status: "not_in_force",
        });
    });

    it("marks a date after the newest snapshot as stale, and the snapshot day itself as not", () => {
        expect(statuteAsOf(m20, LATEST, LATEST)).toMatchObject({ status: "found", stale: false });
        expect(statuteAsOf(m20, "2026-04-23", LATEST)).toMatchObject({
            status: "found",
            stale: true,
        });
    });

    it("prefers a version over a gap that covers the same day", () => {
        const both = [gap("2010-01-01", "2012-01-01"), version("2011-01-01", null)];
        expect(statuteAsOf(both, "2011-06-01", LATEST)).toMatchObject({
            status: "found",
            index: 1,
        });
    });
});
