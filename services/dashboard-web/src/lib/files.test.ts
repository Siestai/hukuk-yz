import { describe, expect, it } from "vitest";

import { readRepoFile, schemaEnum } from "@/test/reason-codes";
import {
    ACCEPT,
    activeFileFilters,
    ALLOWED_EXTENSIONS,
    changeFileParams,
    DOC_TYPES,
    fileApiQuery,
    fileListHref,
    parseFileParams,
    readScan,
    REVIEW_STATUSES,
    SCAN_STATUSES,
    webLink,
} from "./files";

describe("file constants", () => {
    it("lists the document types and scan states of the API", () => {
        expect([...DOC_TYPES].sort()).toEqual(schemaEnum("FileOut", "doc_type").sort());
        expect([...SCAN_STATUSES].sort()).toEqual(schemaEnum("FileOut", "scan_status").sort());
        expect([...REVIEW_STATUSES].sort()).toEqual(schemaEnum("FileOut", "review_status").sort());
    });

    it("accepts the extensions the API allows", () => {
        const source = readRepoFile("services/app/app/files/api.py");
        const block = /ALLOWED_SUFFIXES = frozenset\(\s*\{([^}]*)\}/.exec(source)?.[1] ?? "";
        const api = [...block.matchAll(/"(\.\w+)"/g)].map((m) => m[1]);
        expect([...ALLOWED_EXTENSIONS].sort()).toEqual(api.sort());
        expect(ACCEPT).toBe(".pdf,.doc,.docx,.udf,.png,.jpg,.jpeg,.xlsx,.xlsm,.txt");
    });
});

describe("file list state", () => {
    it("reads the filters, the search and the cursor from the URL", () => {
        const params = parseFileParams(
            new URLSearchParams("tur=genelge&durum=done&q=%202020%2F39%20&imlec=abc_-="),
        );
        expect(params).toEqual({
            docType: "genelge",
            scan: "done",
            q: "2020/39",
            cursor: "abc_-=",
        });
    });

    it("reads the pending tab, asks the API for it, and does not count it as a filter", () => {
        const params = parseFileParams(new URLSearchParams("onay=bekliyor&tur=genelge"));
        expect(params.review).toBe("pending");
        expect(fileListHref(params)).toBe("/dosyalar?tur=genelge&onay=bekliyor");
        expect(fileApiQuery(params).review_status).toBe("pending");
        expect(activeFileFilters(params)).toBe(1);
        expect(parseFileParams(new URLSearchParams("onay=x")).review).toBeUndefined();
        expect(fileApiQuery({}).review_status).toBeUndefined();
    });

    it("ignores unknown values and a malformed cursor", () => {
        expect(parseFileParams({ tur: "x", durum: ["done", "failed"], imlec: "a b/c" })).toEqual({
            docType: undefined,
            scan: "done",
            q: undefined,
            cursor: undefined,
        });
    });

    it("writes only what is set, and a change goes back to the first page", () => {
        expect(fileListHref({})).toBe("/dosyalar");
        const params = { docType: "karar", cursor: "abc" } as const;
        expect(fileListHref(params)).toBe("/dosyalar?tur=karar&imlec=abc");
        expect(fileListHref(changeFileParams(params, { scan: "failed" }))).toBe(
            "/dosyalar?tur=karar&durum=failed",
        );
    });

    it("counts the filters, not the cursor, and builds the API query", () => {
        expect(activeFileFilters({ docType: "karar", cursor: "abc" })).toBe(1);
        expect(fileApiQuery({ scan: "queued", q: "x", cursor: "abc" })).toEqual({
            doc_type: undefined,
            scan_status: "queued",
            q: "x",
            cursor: "abc",
            limit: 25,
        });
    });
});

describe("readScan", () => {
    it("reads the worker's result and leaves out the ocr marker from the warnings", () => {
        expect(
            readScan({
                detected_type: "pdf",
                pages: 3,
                text_chars: 10,
                ocr_used: true,
                warnings: ["ocr", "empty_pages", 7],
                text_key: "text/x.txt",
                error: "boom",
            }),
        ).toEqual({
            detectedType: "pdf",
            pages: 3,
            textChars: 10,
            ocrUsed: true,
            warnings: ["empty_pages"],
            error: "boom",
            hasText: true,
        });
    });

    it("copes with no result and with values of the wrong type", () => {
        const empty = { ocrUsed: false, warnings: [], hasText: false };
        expect(readScan(null)).toMatchObject(empty);
        expect(readScan({ pages: "3", warnings: "x", text_key: 1 })).toMatchObject(empty);
    });
});

describe("webLink", () => {
    it.each([
        ["https://example.org/a", "https://example.org/a"],
        ["http://example.org", "http://example.org"],
        ["javascript:alert(1)", null],
        ["data:text/html,x", null],
        ["not a url", null],
        ["", null],
        [null, null],
    ])("%j links to %j", (value, expected) => {
        expect(webLink(value)).toBe(expected);
    });
});
