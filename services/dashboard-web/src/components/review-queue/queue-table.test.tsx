import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import type { QueueParams } from "@/lib/queue-params";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { QueueTable, type QueueItem } from "./queue-table";

const item: QueueItem = {
    extraction_id: "e1",
    source_status: "analyzed",
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

const queue: QueueParams = { sort: "score_asc", page: 1 };

function renderRow(overrides: Partial<QueueItem> = {}) {
    renderWithIntl(<QueueTable items={[{ ...item, ...overrides }]} params={queue} />);
    return screen.getAllByRole("row")[1] as HTMLElement;
}

describe("QueueTable", () => {
    it("renders the fields of a decision", () => {
        const row = renderRow();
        expect(within(row).getByText(messages.enums.band.medium)).toBeInTheDocument();
        expect(within(row).getByText("75")).toBeInTheDocument();
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

    it("links the title to the detail screen with the queue state", () => {
        renderWithIntl(
            <QueueTable
                items={[item]}
                params={{ band: "low", court: "yargitay", sort: "score_desc", page: 3 }}
            />,
        );
        expect(screen.getByRole("link", { name: "KIDEM TAZMİNATI" })).toHaveAttribute(
            "href",
            "/kararlar/e1?band=low&court=yargitay&sort=score_desc&page=3&pos=100",
        );
    });

    it("links without a query when the queue state is the default", () => {
        expect(within(renderRow()).getByRole("link")).toHaveAttribute("href", "/kararlar/e1?pos=0");
    });

    it("carries the absolute queue position of each row", () => {
        renderWithIntl(
            <QueueTable
                items={[item, { ...item, extraction_id: "e2", title: "IKINCI" }]}
                params={{ sort: "score_asc", page: 2 }}
            />,
        );
        expect(screen.getByRole("link", { name: "IKINCI" })).toHaveAttribute(
            "href",
            "/kararlar/e2?page=2&pos=51",
        );
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

    it("renders one row and one link per item", () => {
        renderWithIntl(
            <QueueTable
                items={[item, { ...item, extraction_id: "e2" }, { ...item, extraction_id: "e3" }]}
                params={queue}
            />,
        );
        expect(screen.getAllByRole("row")).toHaveLength(4);
        expect(screen.getAllByRole("link")).toHaveLength(3);
    });
});

describe("QueueTable help", () => {
    const { table, help } = {
        table: messages.review.queue.table,
        help: messages.review.queue.help,
    };

    it.each([
        table.confidence,
        table.decision,
        table.court,
        table.numbers,
        table.date,
        table.issue,
        table.reasons,
    ])("has a tip in the %s column header", (label) => {
        renderRow();
        const header = screen.getByRole("columnheader", { name: new RegExp(`^${label}`) });
        expect(within(header).getByRole("button", { name: `Bilgi: ${label}` })).toBeInTheDocument();
    });

    it("explains the two numbers, in the column that shows them", async () => {
        renderRow();
        await userEvent.click(infoTip(table.numbers));
        expect(openTipText()).toHaveTextContent(help.colNumbers);
    });

    it("explains the duplicate marker in the decision column tip", () => {
        expect(help.colDecision).toContain("Mükerrer");
    });

    it("describes a known reason for screen readers, without a tip in the row", () => {
        const row = renderRow({ reasons: ["date_from_closing"] });
        const badge = within(row).getByText(messages.enums.reason.date_from_closing);
        expect(badge).toHaveTextContent(help.reason.date_from_closing);
        expect(within(row).queryByRole("button")).toBeNull();
    });

    describe("the review columns of the status tabs", () => {
        const { table } = messages.review.queue;
        const reviewed: Partial<QueueItem> = {
            source_status: "approved",
            reviewed_at: "2026-10-04T09:30:00Z",
            reviewer_name: "Baran",
            review_decision: "approve",
        };
        const rejected: Partial<QueueItem> = {
            source_status: "rejected",
            reviewed_at: "2026-10-04T09:30:00Z",
            reviewer_name: "İbrahim",
            review_decision: "reject",
            note: "Kopya kayıt, aynı karar başka sayıda var.",
        };
        const headers = () => screen.getAllByRole("columnheader").map((h) => h.textContent);

        function setup(status: QueueParams["status"], overrides: Partial<QueueItem>) {
            renderWithIntl(
                <QueueTable
                    items={[{ ...item, ...overrides }]}
                    params={{ status, sort: "reviewed_desc", page: 1 }}
                />,
            );
            return screen.getAllByRole("row")[1] as HTMLElement;
        }

        it("adds nothing to the queue", () => {
            renderRow();
            expect(headers()).toHaveLength(7);
        });

        it("approved: a status badge and the review", () => {
            const row = setup("approved", { ...reviewed, review_decision: "edit" });
            expect(headers().slice(7)).toEqual([
                expect.stringContaining(table.status),
                expect.stringContaining(table.review),
            ]);
            expect(within(row).getByText(table.statuses.edited)).toBeInTheDocument();
            expect(within(row).getByText("Baran")).toBeInTheDocument();
            expect(within(row).getByText(/04\.10\.2026/)).toBeInTheDocument();
            expect(screen.getByRole("table")).toHaveAccessibleName(table.labels.approved);
        });

        it("approved without corrections says plainly approved", () => {
            const row = setup("approved", reviewed);
            expect(within(row).getByText(table.statuses.approved)).toBeInTheDocument();
        });

        it("rejected: the review and the note, no status column", () => {
            const row = setup("rejected", rejected);
            expect(headers().slice(7)).toEqual([
                expect.stringContaining(table.review),
                expect.stringContaining(table.note),
            ]);
            expect(within(row).getByText("İbrahim")).toBeInTheDocument();
            expect(within(row).getByText(rejected.note as string)).toHaveAttribute(
                "title",
                rejected.note,
            );
        });

        it("all: a badge per row, with the review empty for a waiting record", () => {
            renderWithIntl(
                <QueueTable
                    items={[
                        { ...item, extraction_id: "w" },
                        { ...item, ...rejected, extraction_id: "r" },
                    ]}
                    params={{ status: "all", sort: "score_asc", page: 1 }}
                />,
            );
            expect(headers()).toHaveLength(10);
            const [, waiting, gone] = screen.getAllByRole("row") as HTMLElement[];
            expect(within(waiting!).getByText(table.statuses.pending)).toBeInTheDocument();
            expect(within(waiting!).queryByText("İbrahim")).toBeNull();
            expect(within(gone!).getByText(table.statuses.rejected)).toBeInTheDocument();
            expect(within(gone!).getByText("İbrahim")).toBeInTheDocument();
        });

        it("shows a reviewer without a user row as unknown", () => {
            const row = setup("approved", { ...reviewed, reviewer_name: null });
            expect(within(row).getByText(table.unknownReviewer)).toBeInTheDocument();
        });

        it("gives every extra column a tip", () => {
            setup("all", rejected);
            for (const topic of [table.status, table.review, table.note]) {
                expect(infoTip(topic)).toBeInTheDocument();
            }
        });
    });
});
