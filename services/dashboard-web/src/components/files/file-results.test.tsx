import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { listItem, NEXT_FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import type { FileListParams, FileListResponse } from "@/lib/files";
import { FileResults } from "./file-results";

vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const { list } = messages.files;
const second = {
    ...listItem,
    id: NEXT_FILE_ID,
    original_name: "ucret-tablosu.xlsx",
    doc_type: "hesap_tablosu",
    doc_date: null,
    official_ref: null,
    uploaded_by_name: null,
    scan_status: "queued",
    version_count: 1,
} as const;

async function setup(
    data: FileListResponse = { items: [listItem, second], next_cursor: null },
    params: FileListParams = {},
) {
    const element = await FileResults({ params, list: Promise.resolve({ data }) });
    return renderWithIntl(element);
}

describe("FileResults", () => {
    it("renders the table and the card list of the same files, CSS shows one", async () => {
        const { container } = await setup();
        const table = within(screen.getByRole("table", { name: list.table.label }));
        expect(table.getAllByRole("row")).toHaveLength(3);
        const cards = screen.getByRole("list", { name: list.table.label });
        expect(cards.querySelectorAll(":scope > li")).toHaveLength(2);
        expect(container.querySelector(".hidden.xl\\:block table")).not.toBeNull();
        expect(container.querySelector(".xl\\:hidden ul")).not.toBeNull();
    });

    it("reads a file as name, type, dates, uploader, scan badge and version count", async () => {
        await setup();
        const table = within(screen.getByRole("table"));
        const row = within(table.getByRole("link", { name: "genelge-2020-39.pdf" }).closest("tr")!);
        expect(row.getByText("2020/39")).toBeInTheDocument();
        expect(row.getByText("Genelge")).toBeInTheDocument();
        expect(row.getByText("15.06.2020")).toBeInTheDocument();
        expect(row.getByText("Baran Yılmaz")).toBeInTheDocument();
        expect(row.getByText("Tamamlandı")).toBeInTheDocument();
        expect(row.getByText("2 sürüm")).toBeInTheDocument();
        const other = within(
            table.getByRole("link", { name: "ucret-tablosu.xlsx" }).closest("tr")!,
        );
        expect(other.getByText("Sırada")).toBeInTheDocument();
        expect(other.getByText("Sistem")).toBeInTheDocument();
    });

    it("shows the review state of every file in the table and in the cards", async () => {
        await setup({
            items: [listItem, { ...second, review_status: "pending" }],
            next_cursor: null,
        });
        const table = within(screen.getByRole("table"));
        const approved = within(
            table.getByRole("link", { name: "genelge-2020-39.pdf" }).closest("tr")!,
        );
        expect(approved.getByText(messages.enums.reviewStatus.approved)).toBeInTheDocument();
        const waiting = within(
            table.getByRole("link", { name: "ucret-tablosu.xlsx" }).closest("tr")!,
        );
        expect(waiting.getByText(messages.enums.reviewStatus.pending)).toBeInTheDocument();
        const cards = within(screen.getByRole("list", { name: list.table.label }));
        expect(cards.getByText(messages.enums.reviewStatus.pending)).toBeInTheDocument();
        expect(cards.getByText(messages.enums.reviewStatus.approved)).toBeInTheDocument();
    });

    it("links each file to its detail page", async () => {
        await setup();
        const link = within(screen.getByRole("table")).getByRole("link", {
            name: "ucret-tablosu.xlsx",
        });
        expect(link).toHaveAttribute("href", `/dosyalar/${NEXT_FILE_ID}`);
    });

    it("links to the next page with the cursor and back to the first", async () => {
        await setup({ items: [listItem], next_cursor: "abc" }, { docType: "genelge" });
        expect(screen.getByRole("link", { name: list.pagination.next })).toHaveAttribute(
            "href",
            "/dosyalar?tur=genelge&imlec=abc",
        );
        expect(screen.queryByRole("link", { name: list.pagination.first })).toBeNull();
    });

    it("offers the first page on a later page and no next link on the last", async () => {
        await setup({ items: [listItem], next_cursor: null }, { cursor: "abc" });
        expect(screen.getByRole("link", { name: list.pagination.first })).toHaveAttribute(
            "href",
            "/dosyalar",
        );
        expect(screen.queryByRole("link", { name: list.pagination.next })).toBeNull();
    });

    it("tells apart an empty store, filters that match nothing and a page past the end", async () => {
        const empty = { items: [], next_cursor: null };
        const { unmount } = await setup(empty);
        expect(screen.getByText(list.empty.none)).toBeInTheDocument();
        unmount();
        const filtered = await setup(empty, { scan: "failed" });
        expect(screen.getByText(list.empty.filtered)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: list.empty.clear })).toHaveAttribute(
            "href",
            "/dosyalar",
        );
        filtered.unmount();
        await setup(empty, { cursor: "abc" });
        expect(screen.getByText(list.empty.pastEnd)).toBeInTheDocument();
    });

    it("says nothing waits for approval on an empty pending tab, and keeps the tab when filters are cleared", async () => {
        const empty = { items: [], next_cursor: null };
        const { unmount } = await setup(empty, { review: "pending" });
        expect(screen.getByText(list.empty.pending)).toBeInTheDocument();
        unmount();
        await setup(empty, { review: "pending", scan: "failed" });
        expect(screen.getByRole("link", { name: list.empty.clear })).toHaveAttribute(
            "href",
            "/dosyalar?onay=bekliyor",
        );
    });

    it("shows the message of the API's error code", async () => {
        const element = await FileResults({
            params: {},
            list: Promise.resolve({ error: { code: "validation_error", params: {} } }),
        });
        renderWithIntl(element);
        expect(screen.getByRole("alert")).toHaveTextContent(messages.errors.validation_error);
    });
});
