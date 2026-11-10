import type { JournalScanDetail, JournalScanItem } from "@/lib/journal-scans";

export const scanItem: JournalScanItem = {
    id: "5b0f3c6e-0a9e-4f0e-8c1d-2a7e4b9d1c11",
    job_id: "6f1c1b3e-2a4d-4c43-9d57-0a1b2c3d4e5f",
    trigger: "schedule",
    started_at: "2026-11-14T08:00:00Z",
    finished_at: "2026-11-14T08:12:00Z",
    status: "completed_with_errors",
    new_issues: [91],
    discovered: 70,
    downloaded: 67,
    duplicates: 1,
    queued: 66,
    errors: 2,
};

export const scanDetail: JournalScanDetail = {
    ...scanItem,
    report: {
        issues: [
            {
                issue_no: 91,
                site_count: 70,
                pdf_links: 69,
                downloaded: 67,
                duplicates: 1,
                queued: 66,
                duplicate_candidates: 3,
                errors: [
                    { url: "https://journal.example.test/karar-7/", reason: "pdf_link_missing" },
                    { url: "https://journal.example.test/karar-9/", reason: "http_503" },
                    { url: "https://journal.example.test/karar-11/", reason: "brand_new_reason" },
                ],
            },
        ],
        failure: null,
        archive_max: 90,
        warnings: [],
    },
};
