import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import type { QueueParams } from "@/lib/queue-params";
import { renderWithIntl } from "@/test/intl";
import { QueueCards } from "./queue-cards";
import type { QueueItem } from "./queue-item-format";

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

function renderCard(overrides: Partial<QueueItem> = {}, params: QueueParams = queue) {
    renderWithIntl(<QueueCards items={[{ ...item, ...overrides }]} params={params} />);
    return screen.getAllByRole("listitem")[0] as HTMLElement;
}

describe("QueueCards", () => {
    it("shows the same fields as a table row", () => {
        const card = renderCard();
        expect(within(card).getByText(messages.enums.band.medium)).toBeInTheDocument();
        expect(within(card).getByText("75")).toBeInTheDocument();
        expect(within(card).getByText("KIDEM TAZMİNATI")).toBeInTheDocument();
        expect(within(card).getByText(/Yargıtay · 9\. HD/)).toBeInTheDocument();
        expect(within(card).getByText(/E\. 2019\/1234 · K\. 2021\/567/)).toBeInTheDocument();
        expect(within(card).getByText(/05\.03\.2021/)).toBeInTheDocument();
        expect(within(card).getByText("Sayı 61")).toBeInTheDocument();
        expect(
            within(card).getByText(messages.enums.reason.karar_year_ne_date_year),
        ).toBeInTheDocument();
    });

    it("is one list named like the table, with one link per card", () => {
        renderWithIntl(
            <QueueCards
                items={[item, { ...item, extraction_id: "e2" }, { ...item, extraction_id: "e3" }]}
                params={queue}
            />,
        );
        expect(
            screen.getByRole("list", { name: messages.review.queue.table.label }),
        ).toBeInTheDocument();
        expect(screen.getAllByRole("link")).toHaveLength(3);
    });

    it("links the title to the detail screen with the queue state and the position", () => {
        renderCard({}, { band: "low", court: "yargitay", sort: "score_desc", page: 3 });
        expect(screen.getByRole("link", { name: "KIDEM TAZMİNATI" })).toHaveAttribute(
            "href",
            "/kararlar/e1?band=low&court=yargitay&sort=score_desc&page=3&pos=100",
        );
    });

    it("stretches the link over the whole card", () => {
        const card = renderCard();
        expect(card).toHaveClass("relative");
        expect(within(card).getByRole("link")).toHaveClass("after:absolute", "after:inset-0");
    });

    it("shows dashes for missing numbers, date and issue", () => {
        const card = renderCard({
            esas_no: "",
            karar_no: "",
            decision_date: "",
            journal_issue: null,
        });
        expect(within(card).getByText("- · -")).toBeInTheDocument();
        expect(within(card).getByText("Sayı -")).toBeInTheDocument();
    });

    it("labels an unreadable court", () => {
        const card = renderCard({ court: "", chamber: "" });
        expect(within(card).getByText(messages.enums.court.unknown)).toBeInTheDocument();
    });

    it("shows at most two reasons and the rest as +N, readable by screen readers", () => {
        const card = renderCard({
            reasons: ["missing_esas_no", "missing_karar_no", "duplicate_of", "body_not_found"],
        });
        expect(within(card).getByText(messages.enums.reason.missing_esas_no)).toBeInTheDocument();
        expect(within(card).getByText(messages.enums.reason.missing_karar_no)).toBeInTheDocument();
        expect(within(card).getByText("+2")).toHaveAccessibleDescription(
            [messages.enums.reason.duplicate_of, messages.enums.reason.body_not_found].join(" "),
        );
    });

    it("shows no +N for two reasons or fewer", () => {
        const card = renderCard({ reasons: ["missing_esas_no", "missing_karar_no"] });
        expect(within(card).queryByText(/^\+/)).toBeNull();
    });

    it("marks a duplicate group with an accessible label", () => {
        const card = renderCard({ duplicate_group: { key: "k" } });
        expect(
            within(card).getByRole("img", { name: messages.review.queue.table.duplicate }),
        ).toBeInTheDocument();
    });

    it("has no duplicate marker without a group", () => {
        expect(within(renderCard()).queryByRole("img")).toBeNull();
    });
});

describe("QueueCards help", () => {
    it("describes a known reason for screen readers", () => {
        const card = renderCard({ reasons: ["date_from_closing"] });
        expect(card).toHaveTextContent(messages.review.queue.help.reason.date_from_closing);
        expect(within(card).queryByRole("button")).toBeNull();
    });

    describe("the review lines of the status tabs", () => {
        const { table } = messages.review.queue;
        const rejected: Partial<QueueItem> = {
            source_status: "rejected",
            reviewed_at: "2026-10-04T09:30:00Z",
            reviewer_name: "İbrahim",
            review_decision: "reject",
            note: "Kopya kayıt.",
        };
        const tab = (status: QueueParams["status"]): QueueParams => ({
            status,
            sort: "reviewed_desc",
            page: 1,
        });

        it("adds nothing to the queue", () => {
            const card = renderCard();
            expect(within(card).queryByText(table.statuses.pending)).toBeNull();
            expect(within(card).queryByText(/İnceleme:/)).toBeNull();
        });

        it("shows the badge, the review and the note of a rejection", () => {
            const card = renderCard(rejected, tab("all"));
            expect(within(card).getByText(table.statuses.rejected)).toBeInTheDocument();
            expect(within(card).getByText(/İnceleme: 04\.10\.2026.*İbrahim/)).toBeInTheDocument();
            expect(within(card).getByText("Ret notu: Kopya kayıt.")).toBeInTheDocument();
            expect(screen.getByRole("list", { name: table.labels.all })).toBeInTheDocument();
        });

        it("tells an approval with corrections from a plain one", () => {
            const edited = { source_status: "approved", review_decision: "edit" } as const;
            const card = renderCard({ ...rejected, ...edited, note: null }, tab("approved"));
            expect(within(card).getByText(table.statuses.edited)).toBeInTheDocument();
            expect(within(card).queryByText(/Ret notu/)).toBeNull();
        });

        it("shows a waiting record in the all tab with a badge and no review", () => {
            const card = renderCard({}, tab("all"));
            expect(within(card).getByText(table.statuses.pending)).toBeInTheDocument();
            expect(within(card).queryByText(/İnceleme:/)).toBeNull();
        });

        it("keeps the tab in the link to the detail", () => {
            const card = renderCard(rejected, tab("rejected"));
            expect(within(card).getByRole("link")).toHaveAttribute(
                "href",
                "/kararlar/e1?durum=reddedilen&pos=0",
            );
        });
    });
});
