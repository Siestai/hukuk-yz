import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import type { JournalScanItem } from "@/lib/journal-scans";
import { scanItem } from "@/test/journal-fixtures";
import { renderWithIntl } from "@/test/intl";
import { ScanCards } from "./scan-cards";
import { ScanTable } from "./scan-table";

const { table } = messages.journalScans.list;
const failed: JournalScanItem = {
    ...scanItem,
    id: "7c2d4e8f-1b3a-4d5c-9e6f-0a1b2c3d4e5f",
    status: "failed",
    trigger: "manual",
    new_issues: [],
    errors: 0,
};

describe("ScanTable", () => {
    it("shows the time in Istanbul, who started it, the status and the numbers", () => {
        renderWithIntl(<ScanTable items={[scanItem, failed]} />);
        const row = screen.getAllByRole("row")[1] as HTMLElement;
        expect(within(row).getByRole("link", { name: "14.11.2026 11:00" })).toHaveAttribute(
            "href",
            `/taramalar/${scanItem.id}`,
        );
        expect(within(row).getByText(messages.enums.journalTrigger.schedule)).toBeInTheDocument();
        expect(
            within(row).getByText(messages.enums.journalStatus.completed_with_errors),
        ).toBeInTheDocument();
        const cells = within(row)
            .getAllByRole("cell")
            .map((cell) => cell.textContent);
        expect(cells.slice(3)).toEqual(["91", "70", "66", "1", "2"]);
        const second = screen.getAllByRole("row")[2] as HTMLElement;
        expect(within(second).getByText(messages.enums.journalTrigger.manual)).toBeInTheDocument();
        expect(within(second).getByText(messages.enums.journalStatus.failed)).toBeInTheDocument();
        expect(within(second).getAllByRole("cell")[3]).toHaveTextContent(messages.common.empty);
    });

    it("names its columns", () => {
        renderWithIntl(<ScanTable items={[scanItem]} />);
        for (const label of [
            table.time,
            table.trigger,
            table.status,
            table.newIssues,
            table.discovered,
            table.queued,
            table.duplicates,
            table.errors,
        ]) {
            expect(screen.getByRole("columnheader", { name: label })).toBeInTheDocument();
        }
    });
});

describe("ScanCards", () => {
    it("shows the same fields as a table row, one link each", () => {
        renderWithIntl(<ScanCards items={[scanItem]} />);
        const card = screen.getAllByRole("listitem")[0] as HTMLElement;
        expect(within(card).getByRole("link", { name: "14.11.2026 11:00" })).toHaveAttribute(
            "href",
            `/taramalar/${scanItem.id}`,
        );
        expect(
            within(card).getByText(messages.enums.journalStatus.completed_with_errors),
        ).toBeInTheDocument();
        expect(within(card).getByText(messages.enums.journalTrigger.schedule)).toBeInTheDocument();
        const numbers = {
            [table.discovered]: "70",
            [table.queued]: "66",
            [table.duplicates]: "1",
            [table.errors]: "2",
        };
        for (const [label, value] of Object.entries(numbers)) {
            expect(within(card).getByText(label).nextSibling).toHaveTextContent(value);
        }
        expect(within(card).getByText(/91/)).toBeInTheDocument();
    });
});
