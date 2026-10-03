import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { readFields } from "@/lib/decision-fields";
import { renderWithIntl } from "@/test/intl";
import { FieldsCard } from "./fields-card";

const full = {
    court: "yargitay",
    court_level: "daire",
    chamber: "9. HD",
    bam_region: "",
    esas_no: "2019/1234",
    karar_no: "2021/567",
    decision_date: "2021-01-01",
    related_articles: [
        { statute: 4857, label: "4857 SK", articles: ["18", "17/3"], raw: "4857 S. İşK/18,17/3" },
        { statute: null, label: "", articles: [], raw: "Bilinmeyen Kanun/5" },
        { statute: 6098, label: "6098 SK", articles: [], raw: "" },
    ],
    outcome: "duzelterek_onama",
    keywords: ["kıdem tazminatı", "fesih"],
    journal_issue: 61,
};

const row = (label: string) =>
    screen
        .getAllByText(label)
        .find((element) => element.tagName === "DT")
        ?.closest("div") as HTMLElement;

describe("FieldsCard", () => {
    it("shows every field with its label and formatting", () => {
        renderWithIntl(<FieldsCard fields={readFields(full)} />);
        expect(within(row(messages.fields.court)).getByText("Yargıtay")).toBeInTheDocument();
        expect(within(row(messages.fields.court_level)).getByText("Daire")).toBeInTheDocument();
        expect(within(row(messages.fields.chamber)).getByText("9. HD")).toBeInTheDocument();
        expect(within(row(messages.fields.esas_no)).getByText("2019/1234")).toHaveClass(
            "font-mono",
        );
        expect(within(row(messages.fields.karar_no)).getByText("2021/567")).toHaveClass(
            "font-mono",
        );
        expect(
            within(row(messages.fields.decision_date)).getByText("01.01.2021"),
        ).toBeInTheDocument();
        expect(
            within(row(messages.fields.outcome)).getByText("Düzelterek onama"),
        ).toBeInTheDocument();
        expect(within(row(messages.fields.keywords)).getAllByRole("listitem")).toHaveLength(2);
        expect(within(row(messages.fields.journal_issue)).getByText("61")).toBeInTheDocument();
        expect(screen.queryByText(messages.fields.bam_region)).toBeNull();
    });

    it("writes related articles as statute and article numbers, raw text for an unmapped statute", () => {
        renderWithIntl(<FieldsCard fields={readFields(full)} />);
        const items = within(row(messages.fields.related_articles)).getAllByRole("listitem");
        expect(items.map((i) => i.textContent)).toEqual([
            "4857 s. Kanun m. 18, 17/3",
            "Bilinmeyen Kanun/5",
            "6098 s. Kanun",
        ]);
    });

    it("shows the BAM region when there is one", () => {
        renderWithIntl(<FieldsCard fields={readFields({ ...full, bam_region: "İstanbul" })} />);
        expect(within(row(messages.fields.bam_region)).getByText("İstanbul")).toBeInTheDocument();
    });

    it("shows a dash for every empty value", () => {
        renderWithIntl(<FieldsCard fields={readFields({})} />);
        const labels = [
            "court",
            "court_level",
            "chamber",
            "esas_no",
            "karar_no",
            "decision_date",
            "related_articles",
            "outcome",
            "keywords",
            "journal_issue",
        ] as const;
        for (const name of labels) {
            expect(within(row(messages.fields[name])).getByText("-")).toBeInTheDocument();
        }
    });

    it("ignores values of the wrong type instead of crashing", () => {
        const fields = readFields({
            court: 5,
            related_articles: "x",
            keywords: [1, "a"],
            journal_issue: "9",
        });
        expect(fields).toMatchObject({
            court: "",
            relatedArticles: [],
            keywords: ["a"],
            journalIssue: null,
        });
    });
});
