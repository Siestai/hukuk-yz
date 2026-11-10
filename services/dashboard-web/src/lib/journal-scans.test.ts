import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { readRepoFile, schemaEnum } from "@/test/reason-codes";
import {
    parseScanPage,
    readJournal,
    readReason,
    readWarning,
    scanApiQuery,
    scanListHref,
    SCAN_PAGE_SIZE,
    SCAN_STATUSES,
    SCAN_TRIGGERS,
    splitFailure,
} from "./journal-scans";

describe("journal scan constants", () => {
    it("lists the statuses and triggers of the API, each with a label", () => {
        expect([...SCAN_STATUSES].sort()).toEqual(schemaEnum("JournalScanItem", "status").sort());
        expect([...SCAN_TRIGGERS].sort()).toEqual(schemaEnum("JournalScanItem", "trigger").sort());
        expect(Object.keys(messages.enums.journalStatus).sort()).toEqual([...SCAN_STATUSES].sort());
        expect(Object.keys(messages.enums.journalTrigger).sort()).toEqual(
            [...SCAN_TRIGGERS].sort(),
        );
    });

    it("has a text for every reason the scan code writes", () => {
        const code = ["client", "scan", "discover", "download"]
            .map((name) => readRepoFile(`services/app/app/journal/${name}.py`))
            .join("\n");
        const written = [
            "pdf_link_missing",
            "not_a_pdf",
            "too_large",
            "timeout",
            "connect_error",
            "not_json",
            "unexpected_answer",
            "unexpected_category",
            "unexpected_post",
            "interrupted",
            "archive_empty",
            "db_error",
        ];
        for (const reason of written) {
            expect(code, reason).toContain(reason);
            expect(readReason(reason), reason).not.toBeNull();
        }
    });
});

describe("readReason", () => {
    it.each([
        ["pdf_link_missing", { key: "pdf_link_missing" }],
        ["not_a_pdf", { key: "not_a_pdf" }],
        ["http_503", { key: "http", status: 503 }],
        ["db_error:IntegrityError", { key: "db_error" }],
        ["error:ValueError", { key: "error" }],
        ["interrupted", { key: "interrupted" }],
    ])("reads %s", (reason, expected) => {
        expect(readReason(reason)).toEqual(expected);
    });

    it("leaves a reason it does not know to be shown as it is", () => {
        expect(readReason("something_new")).toBeNull();
        expect(readReason("http_5")).toBeNull();
    });
});

describe("splitFailure and readWarning", () => {
    it("splits the address from the reason", () => {
        expect(splitFailure("https://site.test/wp-json/x: http_503")).toEqual({
            url: "https://site.test/wp-json/x",
            reason: "http_503",
        });
        expect(splitFailure("interrupted")).toEqual({ url: "", reason: "interrupted" });
    });

    it("reads the archive warning", () => {
        expect(readWarning("archive_max_above_site:92")).toEqual({
            key: "archive_max_above_site",
            value: "92",
        });
        expect(readWarning("other")).toBeNull();
    });
});

describe("readJournal", () => {
    it("takes the issue and the page when they have the right type", () => {
        expect(readJournal({ issue_no: 91, page_url: "https://x.test/a" })).toEqual({
            issueNo: 91,
            pageUrl: "https://x.test/a",
        });
        expect(readJournal({ issue_no: "91", page_url: 3 })).toEqual({
            issueNo: undefined,
            pageUrl: undefined,
        });
        expect(readJournal(null)).toEqual({ issueNo: undefined, pageUrl: undefined });
    });
});

describe("scan list state", () => {
    it("reads the page and asks the API for its offset", () => {
        expect(parseScanPage(new URLSearchParams("page=3"))).toBe(3);
        expect(parseScanPage(new URLSearchParams("page=x"))).toBe(1);
        expect(scanApiQuery(3)).toEqual({ limit: SCAN_PAGE_SIZE, offset: 2 * SCAN_PAGE_SIZE });
        expect(scanListHref(1)).toBe("/taramalar");
        expect(scanListHref(2)).toBe("/taramalar?page=2");
    });
});
