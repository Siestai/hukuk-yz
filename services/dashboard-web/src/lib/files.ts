import type { components } from "@/lib/api/schema";
import { MAX_QUERY_LENGTH, oneOf, pick, type RawParams } from "@/lib/queue-params";

export type FileOut = components["schemas"]["FileOut"];
export type FileListItem = components["schemas"]["FileListItem"];
export type FileListResponse = components["schemas"]["FileListResponse"];
export type FileDetail = components["schemas"]["FileDetail"];
export type DocType = NonNullable<FileOut["doc_type"]>;
export type ScanStatus = FileOut["scan_status"];
export type ReviewStatus = FileOut["review_status"];

export const DOC_TYPES = [
    "kanun",
    "cbk",
    "yonetmelik",
    "teblig",
    "genelge",
    "genel_yazi",
    "ic_emri",
    "karar",
    "kitap",
    "hesap_tablosu",
    "gorus",
    "diger",
] as const satisfies readonly DocType[];

export const SCAN_STATUSES = [
    "queued",
    "running",
    "done",
    "needs_ocr",
    "unsupported",
    "failed",
] as const satisfies readonly ScanStatus[];

export const REVIEW_STATUSES = ["pending", "approved"] as const satisfies readonly ReviewStatus[];

/** Scans that are still on their way: the screens refresh themselves while one is in this state. */
export const ACTIVE_SCANS: readonly ScanStatus[] = ["queued", "running"];

/** The extensions the API accepts (`ALLOWED_SUFFIXES` in `app.files.api`); the API still checks the content. */
export const ALLOWED_EXTENSIONS = [
    ".pdf",
    ".doc",
    ".docx",
    ".udf",
    ".png",
    ".jpg",
    ".jpeg",
    ".xlsx",
    ".xlsm",
    ".txt",
] as const;
export const ACCEPT = ALLOWED_EXTENSIONS.join(",");

/** Warnings of a scan with a label of their own; the "ocr" warning is shown as the OCR flag instead. */
export const SCAN_WARNINGS = [
    "ocr_unavailable",
    "lone_surrogates",
    "too_little_text",
    "borderline_quality",
    "empty_pages",
    "weak_page_text",
] as const;

/** The API stores the origin address as typed; only an http(s) address becomes a link. */
export function webLink(value: string | null): string | null {
    if (!value) return null;
    try {
        const { protocol } = new URL(value);
        return protocol === "http:" || protocol === "https:" ? value : null;
    } catch {
        return null;
    }
}

export const FILE_PAGE_SIZE = 25;

export const fileHref = (id: string) => `/dosyalar/${id}`;
export const contentUrl = (id: string) => `/api/files/${id}/content`;

// --- list state in the URL ---------------------------------------------------------------------

export type FileListParams = {
    docType?: DocType;
    scan?: ScanStatus;
    /** The "Onay bekliyor" tab; without it every file is listed. */
    review?: "pending";
    q?: string;
    cursor?: string;
};

const PENDING_PARAM = "bekliyor";
const CURSOR = /^[A-Za-z0-9_=-]{1,100}$/;

/** Reads the list state from a URL; anything unknown or malformed is ignored. */
export function parseFileParams(raw: RawParams): FileListParams {
    const q = pick(raw, "q")?.trim().slice(0, MAX_QUERY_LENGTH);
    const cursor = pick(raw, "imlec");
    return {
        docType: oneOf(DOC_TYPES, pick(raw, "tur")),
        scan: oneOf(SCAN_STATUSES, pick(raw, "durum")),
        review: pick(raw, "onay") === PENDING_PARAM ? "pending" : undefined,
        q: q || undefined,
        cursor: cursor && CURSOR.test(cursor) ? cursor : undefined,
    };
}

export function serializeFileParams(params: FileListParams): URLSearchParams {
    const query = new URLSearchParams();
    if (params.docType) query.set("tur", params.docType);
    if (params.scan) query.set("durum", params.scan);
    if (params.review) query.set("onay", PENDING_PARAM);
    if (params.q) query.set("q", params.q);
    if (params.cursor) query.set("imlec", params.cursor);
    return query;
}

export function fileListHref(params: FileListParams): string {
    const query = serializeFileParams(params).toString();
    return query ? `/dosyalar?${query}` : "/dosyalar";
}

/** A change of a filter starts again from the first page. */
export function changeFileParams(
    params: FileListParams,
    change: Partial<FileListParams>,
): FileListParams {
    return { ...params, cursor: undefined, ...change };
}

export function activeFileFilters(params: FileListParams): number {
    return [params.docType, params.scan, params.q].filter(Boolean).length;
}

export function fileApiQuery(params: FileListParams) {
    return {
        doc_type: params.docType,
        scan_status: params.scan,
        review_status: params.review,
        q: params.q,
        cursor: params.cursor,
        limit: FILE_PAGE_SIZE,
    };
}

// --- the scan result ---------------------------------------------------------------------------

export type ScanSummary = {
    detectedType?: string;
    pages?: number;
    textChars?: number;
    ocrUsed: boolean;
    warnings: string[];
    error?: string;
    hasText: boolean;
};

/** The worker's `scan_result` (free-form JSON) as the fields the screen shows; wrong types are dropped. */
export function readScan(result: FileOut["scan_result"]): ScanSummary {
    const raw = result ?? {};
    const text = (key: string) => (typeof raw[key] === "string" ? raw[key] : undefined);
    const count = (key: string) => (typeof raw[key] === "number" ? raw[key] : undefined);
    const warnings = Array.isArray(raw.warnings)
        ? raw.warnings.filter((w): w is string => typeof w === "string" && w !== "ocr")
        : [];
    return {
        detectedType: text("detected_type"),
        pages: count("pages"),
        textChars: count("text_chars"),
        ocrUsed: raw.ocr_used === true,
        warnings,
        error: text("error"),
        hasText: text("text_key") !== undefined,
    };
}
