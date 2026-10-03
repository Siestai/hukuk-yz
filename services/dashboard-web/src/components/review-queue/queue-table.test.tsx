import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { QueueTable, type QueueItem } from "./queue-table";

const item: QueueItem = {
    extraction_id: "e1",
    source_id: "s1",
    title: "KIDEM TAZMİNATI",
    court: "yargitay",
    chamber: "9. HD",
    esas_no: "2019/1234",
    karar_no: "2021/567",
    decision_date: "2021-03-05",
    journal_issue: 61,
    band: "medium",
    score: 75,
    reasons: ["karar_year_ne_date_year"],
    duplicate_group: null,
};

function renderRow(overrides: Partial<QueueItem> = {}) {
    renderWithIntl(<QueueTable items={[{ ...item, ...overrides }]} />);
    return screen.getAllByRole("row")[1] as HTMLElement;
}

describe("QueueTable", () => {
    it("renders the fields of a decision", () => {
        const row = renderRow();
        expect(within(row).getByText(messages.enums.band.medium)).toBeInTheDocument();
        expect(within(row).getByText("75,00")).toBeInTheDocument();
        expect(within(row).getByText("KIDEM TAZMİNATI")).toBeInTheDocument();
        expect(within(row).getByText("9. HD")).toBeInTheDocument();
        expect(within(row).getByText(messages.enums.court.yargitay)).toBeInTheDocument();
        expect(within(row).getByText("E. 2019/1234 · K. 2021/567")).toBeInTheDocument();
        expect(within(row).getByText("05.03.2021")).toBeInTheDocument();
        expect(within(row).getByText("61")).toBeInTheDocument();
        expect(
            within(row).getByText(messages.enums.reason.karar_year_ne_date_year),
        ).toBeInTheDocument();
    });

    it("shows dashes for missing numbers, date and issue", () => {
        const row = renderRow({
            esas_no: "",
            karar_no: "",
            decision_date: "",
            journal_issue: null,
        });
        expect(within(row).getAllByText("-")).toHaveLength(3);
    });

    it("shows only the number that exists", () => {
        const row = renderRow({ esas_no: "", karar_no: "2021/567" });
        expect(within(row).getByText("K. 2021/567")).toBeInTheDocument();
    });

    it("labels an unreadable court", () => {
        const row = renderRow({ court: "" });
        expect(within(row).getByText(messages.enums.court.unknown)).toBeInTheDocument();
    });

    it("shows at most two reasons and the rest as +N", () => {
        const row = renderRow({
            reasons: ["missing_esas_no", "missing_karar_no", "duplicate_of", "body_not_found"],
        });
        expect(within(row).getByText(messages.enums.reason.missing_esas_no)).toBeInTheDocument();
        expect(within(row).getByText(messages.enums.reason.missing_karar_no)).toBeInTheDocument();
        const more = within(row).getByText("+2");
        const rest = [messages.enums.reason.duplicate_of, messages.enums.reason.body_not_found];
        expect(more).toHaveAccessibleDescription(rest.join(" "));
        expect(more).not.toHaveAttribute("title");
    });

    it("lists all reasons in one list, the hidden ones for screen readers only", () => {
        const row = renderRow({
            reasons: ["missing_esas_no", "missing_karar_no", "duplicate_of", "body_not_found"],
        });
        const lists = within(row).getAllByRole("list", { hidden: true });
        expect(lists).toHaveLength(2);
        expect(lists[0]?.children).toHaveLength(3);
        expect(lists[1]).toHaveClass("sr-only");
        expect(lists[1]?.children).toHaveLength(2);
    });

    it("keeps the whole title in the DOM and as a tooltip when it is clamped", () => {
        const title = "KIDEM TAZMİNATI ".repeat(20).trim();
        const row = renderRow({ title });
        expect(within(row).getByText(title)).toHaveAttribute("title", title);
    });

    it("does not shift a date-only value across a timezone", () => {
        expect(
            within(renderRow({ decision_date: "2021-01-01" })).getByText("01.01.2021"),
        ).toBeInTheDocument();
    });

    it("shows no +N for two reasons or fewer", () => {
        const row = renderRow({ reasons: ["missing_esas_no", "missing_karar_no"] });
        expect(within(row).queryByText(/^\+/)).toBeNull();
    });

    it("shows the raw code of an unknown reason with a generic hint", () => {
        const row = renderRow({ reasons: ["brand_new_reason"] });
        const badge = within(row).getByText("brand_new_reason", { exact: false });
        expect(badge).toHaveAttribute("title", messages.review.queue.table.unknownReason);
        expect(badge).toHaveTextContent(messages.review.queue.table.unknownReason);
    });

    it("marks a duplicate group with an accessible label", () => {
        const row = renderRow({ duplicate_group: { key: "k" } });
        expect(
            within(row).getByRole("img", { name: messages.review.queue.table.duplicate }),
        ).toBeInTheDocument();
    });

    it("has no duplicate marker without a group", () => {
        expect(within(renderRow()).queryByRole("img")).toBeNull();
    });

    it("renders one row per item and no links", () => {
        renderWithIntl(
            <QueueTable
                items={[item, { ...item, extraction_id: "e2" }, { ...item, extraction_id: "e3" }]}
            />,
        );
        expect(screen.getAllByRole("row")).toHaveLength(4);
        expect(screen.queryByRole("link")).toBeNull();
    });
});
