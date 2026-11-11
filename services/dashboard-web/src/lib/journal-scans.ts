import type { components } from "@hukuk/web-core/api/schema";
import { positiveInt, type RawParams, pick, MAX_PAGE } from "@/lib/queue-params";

export type JournalScanItem = components["schemas"]["JournalScanItem"];
export type JournalScanDetail = components["schemas"]["JournalScanDetail"];
export type JournalScanList = components["schemas"]["JournalScanListResponse"];
export type JournalIssueReport = components["schemas"]["JournalIssueReport"];
export type ScanStatus = JournalScanItem["status"];
type ScanTrigger = JournalScanItem["trigger"];

export const SCAN_STATUSES = [
    "running",
    "completed",
    "completed_with_errors",
    "failed",
] as const satisfies readonly ScanStatus[];
export const SCAN_TRIGGERS = ["schedule", "manual"] as const satisfies readonly ScanTrigger[];

export const SCAN_PAGE_SIZE = 25;

export const scanHref = (id: string) => `/taramalar/${id}`;

/** Reads the page of the scan list from the URL; anything unknown is the first page. */
export function parseScanPage(raw: RawParams): number {
    return positiveInt(pick(raw, "page"), MAX_PAGE) ?? 1;
}

export function scanListHref(page: number): string {
    return page > 1 ? `/taramalar?page=${page}` : "/taramalar";
}

export function scanApiQuery(page: number) {
    return { limit: SCAN_PAGE_SIZE, offset: (page - 1) * SCAN_PAGE_SIZE };
}

/** The reasons of the report that have a plain-Turkish message under `journalScans.reasons` (`http` apart). */
export const REASON_KEYS = [
    "pdf_link_missing",
    "not_a_pdf",
    "too_large",
    "timeout",
    "connect_error",
    "db_error",
    "error",
    "not_json",
    "unexpected_answer",
    "unexpected_category",
    "unexpected_post",
    "interrupted",
    "archive_empty",
] as const;

type ReasonKey = (typeof REASON_KEYS)[number] | "http";

/**
 * The code of a reason such as `not_a_pdf`, `http_503` or `db_error:IntegrityError`, with the
 * status for an HTTP one; null for a reason this screen has no text for (it is then shown as it is).
 */
export function readReason(reason: string): { key: ReasonKey; status?: number } | null {
    const http = /^http_(\d{3})$/.exec(reason);
    if (http) return { key: "http", status: Number(http[1]) };
    const code = reason.split(":", 1)[0] ?? reason;
    const key = REASON_KEYS.find((candidate) => candidate === code);
    return key ? { key } : null;
}

/**
 * The scan's failure is `interrupted` or the address that did not answer and why
 * (`https://site/wp-json/...: http_503`). Splits the two; the address is empty for the first.
 */
export function splitFailure(failure: string): { url: string; reason: string } {
    const at = failure.lastIndexOf(": ");
    return at < 0
        ? { url: "", reason: failure }
        : { url: failure.slice(0, at), reason: failure.slice(at + 2) };
}

/** The `archive_max_above_site:92` style warnings of the report. */
export function readWarning(
    warning: string,
): { key: "archive_max_above_site"; value: string } | null {
    const [code, value = ""] = warning.split(":", 2);
    return code === "archive_max_above_site" ? { key: code, value } : null;
}

/** The numbers of one issue of the report that the detail screen lists under `journalScans.detail.issues`. */
export const ISSUE_COUNTS = [
    "site_count",
    "pdf_links",
    "downloaded",
    "queued",
    "duplicates",
] as const satisfies readonly (keyof JournalIssueReport)[];

/** The numbers the table and the cards of a scan share. */
export const SCAN_COUNTS = ["discovered", "queued", "duplicates", "errors"] as const;

/** The journal page and issue of a scanned decision, from the detail's free-form `journal` object. */
export function readJournal(journal: { [key: string]: unknown } | null | undefined): {
    issueNo?: number;
    pageUrl?: string;
} {
    const issueNo = journal?.issue_no;
    const pageUrl = journal?.page_url;
    return {
        issueNo: typeof issueNo === "number" ? issueNo : undefined,
        pageUrl: typeof pageUrl === "string" ? pageUrl : undefined,
    };
}
