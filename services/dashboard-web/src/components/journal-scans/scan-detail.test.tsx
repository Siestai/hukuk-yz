import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { scanDetail } from "@/test/journal-fixtures";
import { renderWithIntl } from "@/test/intl";
import { ScanHeader } from "./scan-header";
import { ScanIssues } from "./scan-issues";
import { ScanNotes } from "./scan-notes";
import { ScanSummary } from "./scan-summary";

const { detail, reasons } = messages.journalScans;

describe("ScanSummary", () => {
    it("links to the review queue filtered to the scan's job, on the tab with every status", () => {
        renderWithIntl(<ScanSummary scan={scanDetail} />);
        expect(screen.getByRole("link", { name: detail.summary.decisions })).toHaveAttribute(
            "href",
            `/?durum=tumu&job=${scanDetail.job_id}&sort=reviewed_desc`,
        );
        expect(screen.getByText("14.11.2026 11:00")).toBeInTheDocument();
    });
});

describe("ScanHeader", () => {
    it("shows the time, the status and who started it", () => {
        renderWithIntl(<ScanHeader scan={scanDetail} />);
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
            "Tarama, 14.11.2026 11:00",
        );
        expect(
            screen.getByText(messages.enums.journalStatus.completed_with_errors),
        ).toBeInTheDocument();
        expect(screen.getByRole("link", { name: detail.back })).toHaveAttribute(
            "href",
            "/taramalar",
        );
    });
});

describe("ScanIssues", () => {
    it("reports each issue with its numbers and duplicate candidates", () => {
        renderWithIntl(<ScanIssues issues={scanDetail.report.issues} />);
        const card = screen.getByText("91. sayı").closest("[data-slot=card]") as HTMLElement;
        const expected = {
            [detail.issues.site_count]: "70",
            [detail.issues.pdf_links]: "69",
            [detail.issues.downloaded]: "67",
            [detail.issues.queued]: "66",
            [detail.issues.duplicates]: "1",
            [detail.issues.duplicate_candidates]: "3",
        };
        for (const [label, value] of Object.entries(expected)) {
            expect(within(card).getByText(label).nextSibling).toHaveTextContent(value);
        }
    });

    it("hides the duplicate candidates when there are none", () => {
        const [issue] = scanDetail.report.issues;
        renderWithIntl(
            <ScanIssues issues={[{ ...issue!, duplicate_candidates: 0, errors: [] }]} />,
        );
        expect(screen.queryByText(detail.issues.duplicate_candidates)).toBeNull();
    });

    it("lists the errors as address and reason, in Turkish where known and as the code otherwise", () => {
        renderWithIntl(<ScanIssues issues={scanDetail.report.issues} />);
        expect(screen.getByText(reasons.pdf_link_missing)).toBeInTheDocument();
        expect(screen.getByText(reasons.http.replace("{status}", "503"))).toBeInTheDocument();
        expect(screen.getByText("brand_new_reason")).toBeInTheDocument();
        expect(
            screen.getByRole("link", { name: "https://journal.example.test/karar-7/" }),
        ).toHaveAttribute("rel", expect.stringContaining("noopener"));
    });

    it("says so when the run looked at no issue", () => {
        renderWithIntl(<ScanIssues issues={[]} />);
        expect(screen.getByText(detail.issues.none)).toBeInTheDocument();
    });
});

describe("ScanNotes", () => {
    it("shows nothing for a clean run", () => {
        const { container } = renderWithIntl(
            <ScanNotes report={{ issues: [], failure: null, archive_max: null, warnings: [] }} />,
        );
        expect(container).toBeEmptyDOMElement();
    });

    it("tells why the run failed and which address did not answer", () => {
        renderWithIntl(
            <ScanNotes
                report={{
                    issues: [],
                    failure: "https://journal.example.test/wp-json/x: http_503",
                    archive_max: 90,
                    warnings: ["archive_max_above_site:95", "odd_warning"],
                }}
            />,
        );
        expect(screen.getByRole("alert")).toHaveTextContent(
            detail.notes.failure.replace("{reason}", reasons.http.replace("{status}", "503")),
        );
        expect(screen.getByText("https://journal.example.test/wp-json/x")).toBeInTheDocument();
        expect(screen.getByText(detail.notes.archiveMax.replace("{no}", "90"))).toBeInTheDocument();
        expect(
            screen.getByText(detail.warnings.archive_max_above_site.replace("{max}", "95")),
        ).toBeInTheDocument();
        expect(screen.getByText("odd_warning")).toBeInTheDocument();
    });
});
