import { describe, expect, it } from "vitest";

import { initialValues } from "./file-approval";
import { readSuggestions } from "./file-suggestions";
import { pendingFile } from "@/test/file-fixtures";

const suggestions = readSuggestions(pendingFile.suggestions);

describe("initialValues", () => {
    it("starts from the suggestions where the record holds nothing", () => {
        expect(initialValues(pendingFile, suggestions)).toMatchObject({
            doc_type: "genelge",
            doc_date: "2024-03-01",
        });
    });

    it("keeps what the record already holds over the suggestions", () => {
        const saved = {
            ...pendingFile,
            doc_type: "teblig" as const,
            doc_date: "2024-04-02",
            official_ref: "2024/9",
            title: "Düzeltilmiş başlık",
            note: "not",
        };
        expect(initialValues(saved, suggestions)).toEqual({
            doc_type: "teblig",
            doc_date: "2024-04-02",
            official_ref: "2024/9",
            title: "Düzeltilmiş başlık",
            origin_url: "",
            note: "not",
        });
    });
});
