import { describe, expect, it } from "vitest";

import { buildEdits, initialValues, isRealIsoDate, type FormValues } from "./decision-edits";
import { readFields } from "./decision-fields";

const fields = readFields({
    court: "yargitay",
    court_level: "daire",
    chamber: "9. HD",
    esas_no: "2019/1234",
    karar_no: "2021/567",
    decision_date: "2021-03-05",
    related_articles: [
        { statute: 4857, label: "4857 SK", articles: ["18", "19"], raw: "4857 S. İşK/18-19" },
        { statute: null, label: "Bilinmeyen", articles: [], raw: "Bilinmeyen Kanun" },
    ],
    outcome: "onama",
    keywords: ["fesih", "kıdem"],
});

function edited(change: Partial<FormValues>) {
    return buildEdits(fields, { ...initialValues(fields), ...change });
}

describe("buildEdits", () => {
    it("sends nothing for an untouched form", () => {
        expect(edited({})).toEqual({ edits: {}, errors: {}, ignored: [] });
    });

    it("sends only the fields that changed, trimmed", () => {
        const { edits } = edited({ karar_no: " 2021/999 ", outcome: "bozma" });
        expect(edits).toEqual({ karar_no: "2021/999", outcome: "bozma" });
    });

    it("compares keywords as arrays: one per line, trimmed, empty lines dropped", () => {
        expect(edited({ keywords: "fesih\n\n kıdem \n" }).edits).toEqual({});
        expect(edited({ keywords: "fesih\n\n ihbar \n" }).edits).toEqual({
            keywords: ["fesih", "ihbar"],
        });
    });

    it("keeps the raw line of untouched related articles and leaves it empty for new ones", () => {
        const values = initialValues(fields);
        const [first, second] = values.related_articles;
        const { edits } = edited({
            related_articles: [
                { ...first!, articles: "18, 20" },
                second!,
                { key: 9, statute: "6331", articles: "4,5", source: null },
                { key: 10, statute: "", articles: " ", source: null },
            ],
        });
        expect(edits.related_articles).toEqual([
            { statute: 4857, label: "4857 SK", articles: ["18", "20"], raw: "4857 S. İşK/18-19" },
            { statute: null, label: "Bilinmeyen", articles: [], raw: "Bilinmeyen Kanun" },
            { statute: 6331, label: "", articles: ["4", "5"], raw: "" },
        ]);
    });

    it("sends the list when a row is removed", () => {
        const [first] = initialValues(fields).related_articles;
        expect(edited({ related_articles: [first!] }).edits.related_articles).toHaveLength(1);
    });

    it("refuses to empty esas and karar numbers", () => {
        const { edits, errors } = edited({ esas_no: " ", karar_no: "" });
        expect(edits).toEqual({});
        expect(errors).toEqual({ esas_no: "blank", karar_no: "blank" });
    });

    it("sends nothing for other fields that were emptied, and says so", () => {
        const result = edited({ chamber: "", outcome: "", keywords: "", related_articles: [] });
        expect(result.edits).toEqual({});
        expect(result.errors).toEqual({});
        expect(result.ignored).toEqual(["chamber", "outcome", "keywords", "related_articles"]);
    });

    it("rejects a date that is not real and a statute that is not a number", () => {
        const [first] = initialValues(fields).related_articles;
        const { edits, errors } = edited({
            decision_date: "2021-02-30",
            related_articles: [{ ...first!, statute: "48a7" }],
        });
        expect(errors).toEqual({
            decision_date: "invalid_date",
            related_articles: "invalid_statute",
        });
        expect(edits).toEqual({});
    });
});

describe("isRealIsoDate", () => {
    it.each([
        ["2020-02-29", true],
        ["2019-02-29", false],
        ["2021-13-01", false],
        ["05.03.2021", false],
    ])("%s → %s", (value, expected) => {
        expect(isRealIsoDate(value)).toBe(expected);
    });
});
