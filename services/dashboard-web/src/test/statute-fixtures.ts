import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];

export const STATUTE_ID = "5b1d7a2e-3c44-4d8f-9a61-0e2f7b8c9d10";
export const NEXT_STATUTE_ID = "6c2e8b3f-4d55-4e90-8b72-1f308c9dae21";

/** The shape of 4857 m. 18: a gap before the first copy's amendment, then two versions. */
export const timeline: Schemas["StatuteReviewDetail"]["timeline"] = [
    {
        kind: "gap",
        from: "2003-06-10",
        to: "2014-09-11",
        reason: "before_earliest_snapshot",
        known_amendments: [{ law: "6552", date: "2014-09-10", kind: "ek", scope: "cümle" }],
    },
    {
        kind: "version",
        text: "İşçi bir ay içinde dava açabilir.",
        heading: "Feshin geçerli sebebe dayandırılması",
        valid_from: "2014-09-11",
        valid_to: "2018-01-01",
        change_kind: "amended",
        amending_ref: "6552 (10/9/2014)",
        evidence: {
            basis: "act",
            snapshots: ["Mevzuat/Kanunlar/4857 sayılı İş Kanunu 13.05.2016 .docx"],
            snapshot_dates: ["2016-05-13"],
            amendments: "6552 (10/9/2014)",
        },
        confidence: "medium",
        footnotes: [{ no: 1, text: "5838 sayılı Kanunla eklendi.", page: 2 }],
        warnings: ["exception_effective"],
    },
    {
        kind: "version",
        text: "İşçi arabulucuya başvurduktan sonra bir ay içinde dava açabilir.",
        heading: "Feshin geçerli sebebe dayandırılması",
        valid_from: "2018-01-01",
        valid_to: null,
        change_kind: "amended",
        amending_ref: "7036 (12/10/2017)",
        evidence: {
            basis: "act",
            snapshots: ["Mevzuat/Kanunlar/4857 sayılı İş Kanunu.pdf"],
            snapshot_dates: ["2026-04-22"],
            amendments: "7036 (12/10/2017)",
        },
        confidence: "high",
        footnotes: [],
        warnings: [],
    },
];

export const LATEST = "2026-04-22";

export const detail: Schemas["StatuteReviewDetail"] = {
    extraction_id: STATUTE_ID,
    source_id: "src-1",
    source_status: "analyzed",
    statute_number: "4857",
    statute_title: "4857 sayılı İş Kanunu",
    article_no: "18",
    ordinal: 18,
    heading: "Feshin geçerli sebebe dayandırılması",
    status: "pending",
    band: "medium",
    reasons: ["exception_effective", "before_earliest_snapshot"],
    warnings: ["exception_effective", "before_earliest_snapshot", "footnote_marker_not_found"],
    timeline,
    snapshots: [{ file_name: "4857 sayılı İş Kanunu.pdf", date: LATEST }],
    latest_snapshot_date: LATEST,
    reviews: [],
    live_extraction_id: null,
};

export const listItem: Schemas["StatuteReviewListItem"] = {
    extraction_id: STATUTE_ID,
    source_id: "src-1",
    statute_number: "4857",
    article_no: "18",
    ordinal: 18,
    heading: "Feshin geçerli sebebe dayandırılması",
    band: "medium",
    reasons: ["multi_amendment_in_window", "exception_effective"],
    version_count: 3,
    gap_count: 1,
    latest_snapshot_date: LATEST,
    status: "pending",
};
