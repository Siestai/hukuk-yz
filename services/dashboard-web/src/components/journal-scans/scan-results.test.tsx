import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { formats, timeZone } from "@hukuk/web-core/i18n/formats";
import { scanItem } from "@/test/journal-fixtures";
import { ScanResults } from "./scan-results";

async function show(page: number, answer: Parameters<typeof ScanResults>[0]["list"]) {
    const ui = await ScanResults({ page, list: answer });
    render(
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {ui}
        </NextIntlClientProvider>,
    );
}

const empty = messages.journalScans.list.empty;

describe("ScanResults", () => {
    it("says so when no scan has run", async () => {
        await show(1, Promise.resolve({ data: { total: 0, items: [] } }));
        expect(screen.getByText(empty.none)).toBeInTheDocument();
    });

    it("sends a page past the end back to the first", async () => {
        await show(4, Promise.resolve({ data: { total: 3, items: [] } }));
        expect(screen.getByText(empty.pastEnd)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: empty.first })).toHaveAttribute(
            "href",
            "/taramalar",
        );
    });

    it("renders both the table and the cards, and pages when there is more than a page", async () => {
        await show(2, Promise.resolve({ data: { total: 60, items: [scanItem] } }));
        expect(screen.getAllByRole("link", { name: "14.11.2026 11:00" })).toHaveLength(2);
        expect(
            screen.getByRole("link", { name: messages.journalScans.list.pagination.previous }),
        ).toHaveAttribute("href", "/taramalar");
        expect(
            screen.getByRole("link", { name: messages.journalScans.list.pagination.next }),
        ).toHaveAttribute("href", "/taramalar?page=3");
    });

    it("shows the translated message when the API refuses", async () => {
        await show(1, Promise.resolve({ error: { code: "forbidden", params: {} } } as never));
        expect(screen.getByRole("alert")).toBeInTheDocument();
    });
});
