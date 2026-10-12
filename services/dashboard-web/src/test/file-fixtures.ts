import type { FileListItem, FileOut } from "@/lib/files";

export const FILE_ID = "3f0c9b1e-8a52-4a53-9d7c-2f4f6b1d9a10";
export const NEXT_FILE_ID = "7a1d5c2e-1b34-4c8e-9f60-0d2b8e4a7c11";

/** A scanned PDF with a text layer, uploaded by a reviewer. */
export const file: FileOut = {
    id: FILE_ID,
    original_name: "genelge-2020-39.pdf",
    sha256: "a".repeat(64),
    size: 2_621_440,
    detected_type: "pdf",
    doc_type: "genelge",
    doc_date: "2020-06-15",
    official_ref: "2020/39",
    origin_url: "https://www.sgk.gov.tr/genelge",
    note: null,
    uploaded_by_id: "u1",
    uploaded_by_name: "Baran Yılmaz",
    uploaded_at: "2026-10-11T09:30:00Z",
    supersedes_id: null,
    scan_status: "done",
    scan_result: {
        detected_type: "pdf",
        pages: 3,
        text_chars: 4210,
        ocr_used: false,
        warnings: ["weak_page_text"],
        text_key: "text/aaa.txt",
    },
    archived_at: null,
    review_status: "approved",
    approved_by_id: null,
    approved_at: null,
    title: null,
    suggestions: null,
    matches: null,
};

export const listItem: FileListItem = { ...file, version_count: 2 };

/** A freshly scanned upload waiting for approval, with what the rules read from its text. */
export const pendingFile: FileOut = {
    ...file,
    doc_type: null,
    doc_date: null,
    official_ref: null,
    origin_url: null,
    review_status: "pending",
    suggestions: {
        doc_type: {
            value: "genelge",
            source: "rule",
            evidence: { page: 1, quote: "GENELGE 2024/5" },
        },
        doc_date: {
            value: "2024-03-01",
            source: "rule",
            evidence: { page: 1, quote: "Sayı: E-12345 01.03.2024" },
        },
        official_ref: { value: "2024/5", source: "llm", evidence: null },
    },
    matches: null,
};
