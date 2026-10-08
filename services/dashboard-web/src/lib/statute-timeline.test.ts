import { describe, expect, it } from "vitest";

import type { TimelineVersion } from "./statute-as-of";
import { parseAmendingRef, readEvidence, readFootnotes } from "./statute-timeline";

const version = (overrides: Partial<TimelineVersion>): TimelineVersion => ({
    kind: "version",
    text: "t",
    heading: null,
    valid_from: "2014-09-11",
    valid_to: null,
    change_kind: "amended",
    amending_ref: null,
    evidence: {},
    confidence: "high",
    footnotes: [],
    warnings: [],
    ...overrides,
});

describe("parseAmendingRef", () => {
    it("reads laws with their kabul days", () => {
        expect(parseAmendingRef("6552 (10/9/2014), AYM (19/10/2005)")).toEqual([
            { law: "6552", kabul: "2014-09-10" },
            { law: "AYM", kabul: "2005-10-19" },
        ]);
    });

    it("is empty without a reference, and keeps what it cannot read", () => {
        expect(parseAmendingRef(null)).toEqual([]);
        expect(parseAmendingRef("6552")).toEqual([{ law: "6552", kabul: null }]);
    });
});

describe("readEvidence", () => {
    it("pairs the copies with their dates and takes the file names", () => {
        const evidence = readEvidence(
            version({
                amending_ref: "6552 (10/9/2014)",
                evidence: {
                    basis: "exception",
                    snapshots: ["Mevzuat/Kanunlar/4857.docx", "4857.pdf"],
                    snapshot_dates: ["2016-05-13"],
                    amendments: "6552 (10/9/2014)",
                },
            }),
        );
        expect(evidence.basis).toBe("exception");
        expect(evidence.copies).toEqual([
            { fileName: "4857.docx", date: "2016-05-13" },
            { fileName: "4857.pdf", date: null },
        ]);
        expect(evidence.amendments).toEqual([{ law: "6552", kabul: "2014-09-10" }]);
    });

    it("copes with an empty evidence", () => {
        expect(readEvidence(version({}))).toEqual({ basis: null, copies: [], amendments: [] });
    });
});

describe("readFootnotes", () => {
    it("keeps footnotes of the stored shape and skips others", () => {
        expect(
            readFootnotes(
                version({ footnotes: [{ no: 1, text: "5838 sayılı", page: 2 }, "x", { no: 2 }] }),
            ),
        ).toEqual([{ no: 1, text: "5838 sayılı", page: 2 }]);
    });
});
