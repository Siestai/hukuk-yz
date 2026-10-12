import { describe, expect, it } from "vitest";

import { readRepoFile } from "@/test/reason-codes";
import {
    MATCH_REASONS,
    readMatches,
    readSuggestions,
    SUGGESTION_SOURCES,
} from "./file-suggestions";
import { FILE_ID, NEXT_FILE_ID } from "@/test/file-fixtures";

describe("readSuggestions", () => {
    it("reads value, source and the quote with its page", () => {
        const found = readSuggestions({
            doc_type: {
                value: "genelge",
                source: "rule",
                evidence: { page: 1, quote: "GENELGE 2024/5" },
            },
            doc_date: { value: "2024-03-01", source: "rule", evidence: { file_type: "x" } },
        });
        expect(found.doc_type).toEqual({
            value: "genelge",
            source: "rule",
            quote: { page: 1, text: "GENELGE 2024/5" },
            unsupported: false,
        });
        expect(found.doc_date?.quote).toBeNull();
        expect(found.doc_date?.unsupported).toBe(false);
    });

    it("marks an LLM suggestion without evidence, and only that one", () => {
        const found = readSuggestions({
            doc_type: { value: "genelge", source: "llm", evidence: null },
            title: { value: "Konu", source: "llm", evidence: { page: 2, quote: "Konu" } },
            official_ref: { value: "2024/5", source: "user", evidence: null },
        });
        expect(found.doc_type?.unsupported).toBe(true);
        expect(found.title?.unsupported).toBe(false);
        expect(found.official_ref?.unsupported).toBe(false);
    });

    it("keeps what detection found beside the value the user typed", () => {
        const found = readSuggestions({
            doc_type: {
                value: "kanun",
                source: "user",
                evidence: null,
                detected: { value: "karar", source: "rule", evidence: null },
            },
        });
        expect(found.doc_type?.detected).toEqual({ value: "karar" });
    });

    it("drops entries of the wrong shape, unknown sources and fields without a form field", () => {
        expect(
            readSuggestions({
                doc_type: { value: 5, source: "rule" },
                doc_date: { value: "2024-03-01", source: "robot" },
                official_ref: "2024/5",
                title: { value: "", source: "rule" },
                issuer: { value: "SGK", source: "rule", evidence: null },
            }),
        ).toEqual({});
        expect(readSuggestions(null)).toEqual({});
    });

    it("knows the sources the worker and the upload write", () => {
        expect([...SUGGESTION_SOURCES].sort()).toEqual(["llm", "rule", "user"]);
    });
});

describe("readMatches", () => {
    it("reads the previous version and the similar files", () => {
        expect(
            readMatches({
                previous_version: { file_id: FILE_ID, reason: "same_ref" },
                similar: [{ file_id: NEXT_FILE_ID, score: 0.83, reason: "same_name" }],
            }),
        ).toEqual({
            previous: { fileId: FILE_ID, reason: "same_ref" },
            similar: [{ fileId: NEXT_FILE_ID, score: 0.83, reason: "same_name" }],
        });
    });

    it("drops entries without a valid file id or score, and reads null as no match", () => {
        expect(
            readMatches({
                previous_version: { file_id: "../x", reason: "same_ref" },
                similar: [{ file_id: NEXT_FILE_ID }, { file_id: "x", score: 0.9 }, 4],
            }),
        ).toEqual({ previous: null, similar: [] });
        expect(readMatches(null)).toEqual({ previous: null, similar: [] });
        expect(readMatches({ previous_version: null, similar: [] }).previous).toBeNull();
    });

    it("lists the reasons the worker writes", () => {
        const source = readRepoFile("services/app/app/files/matching.py");
        const api = /SAME_REF, SAME_TITLE, SAME_NAME = "(\w+)", "(\w+)", "(\w+)"/.exec(source);
        expect([...MATCH_REASONS]).toEqual(api?.slice(1));
    });
});
