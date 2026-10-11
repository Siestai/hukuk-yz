import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { LATEST, timeline } from "@/test/statute-fixtures";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { TimelineExplorer } from "./timeline-explorer";

const { dateQuery, version, diff, timeline: texts } = messages.review.statutes;

function setup() {
    return renderWithIntl(<TimelineExplorer timeline={timeline} latestSnapshotDate={LATEST} />);
}
const ask = (day: string) =>
    fireEvent.change(screen.getByLabelText(dateQuery.date), { target: { value: day } });
/** The date query's answer: the status region that is not the hidden live region of an InfoTip. */
const answer = () => {
    const region = screen
        .getAllByRole("status")
        .find((node) => !node.classList.contains("sr-only"));
    if (!region) throw new Error("No date query answer");
    return region;
};
const panel = () =>
    screen.getByText(/Seçili sürüm/).closest("div[data-slot='card']") as HTMLElement;

describe("TimelineExplorer", () => {
    it("opens on the newest version and shows its text, evidence and the difference to the previous one", () => {
        setup();
        expect(panel()).toHaveTextContent("Seçili sürüm: 01.01.2018 → bugün");
        expect(panel().querySelector("p.font-serif")).toHaveTextContent(
            "İşçi arabulucuya başvurduktan sonra bir ay içinde dava açabilir.",
        );
        expect(within(panel()).getByText(messages.enums.evidenceBasis.act)).toBeInTheDocument();
        expect(
            within(panel()).getByText("7036 sayılı Kanun (kabul 12.10.2017)"),
        ).toBeInTheDocument();
        const added = within(panel()).getByText("arabulucuya başvurduktan sonra", {
            selector: "ins",
        });
        expect(added).toBeInTheDocument();
        expect(within(panel()).getByText(diff.legend)).toBeInTheDocument();
    });

    it("shows footnotes and the version's warnings in boxes of their own", () => {
        setup();
        fireEvent.click(screen.getAllByRole("button", { name: /11.09.2014/ })[0] as HTMLElement);
        expect(within(panel()).getByText(version.footnotes)).toBeInTheDocument();
        expect(within(panel()).getByText(/5838 sayılı Kanunla eklendi/)).toBeInTheDocument();
        expect(
            within(panel()).getByText(messages.enums.statuteWarning.exception_effective),
        ).toBeInTheDocument();
        // The difference of the older version spans the gap before it? No: it has no previous version.
        expect(within(panel()).getByText(diff.first)).toBeInTheDocument();
    });

    it("selects and marks the version in force on the date asked for", () => {
        setup();
        ask("2016-06-01");
        expect(panel()).toHaveTextContent("Seçili sürüm: 11.09.2014 → 01.01.2018");
        expect(answer()).toHaveTextContent(
            "Bu tarihte 11.09.2014 → 01.01.2018 aralığındaki metin geçerliydi.",
        );
        expect(screen.getAllByText(texts.queried)).toHaveLength(1);
    });

    it("hands the boundary day to the later version", () => {
        setup();
        ask("2018-01-01");
        expect(panel()).toHaveTextContent("Seçili sürüm: 01.01.2018 → bugün");
        ask("2017-12-31");
        expect(panel()).toHaveTextContent("Seçili sürüm: 11.09.2014 → 01.01.2018");
    });

    it("says there is no text for a date in a gap, marks the gap and shows no version text", () => {
        setup();
        ask("2010-01-01");
        expect(answer()).toHaveTextContent(
            "Bu tarihte metin elde yok: 10.06.2003 → 11.09.2014 aralığı.",
        );
        expect(
            within(screen.getByText(texts.gapNoText).closest("div") as HTMLElement).getByText(
                texts.queried,
            ),
        ).toBeInTheDocument();
        expect(screen.queryByText(/Seçili sürüm/)).not.toBeInTheDocument();
        expect(screen.queryByText(/dava açabilir/)).not.toBeInTheDocument();
        ask("2016-06-01");
        expect(panel()).toHaveTextContent("Seçili sürüm: 11.09.2014 → 01.01.2018");
    });

    it("shows the confidence band of the version found, and warns on a low one", () => {
        setup();
        ask("2016-06-01");
        expect(answer()).toHaveTextContent("Güven: Orta");
        expect(screen.queryByText(dateQuery.lowConfidence)).not.toBeInTheDocument();
        ask("2020-01-01");
        expect(answer()).toHaveTextContent("Güven: Yüksek");
        expect(screen.queryByText(dateQuery.lowConfidence)).not.toBeInTheDocument();
    });

    it("warns that the date limit is not certain when the version found is low", () => {
        renderWithIntl(
            <TimelineExplorer
                timeline={timeline.map((entry) =>
                    entry.kind === "version" ? { ...entry, confidence: "low" as const } : entry,
                )}
                latestSnapshotDate={LATEST}
            />,
        );
        ask("2016-06-01");
        expect(answer()).toHaveTextContent("Güven: Düşük");
        expect(screen.getByText(dateQuery.lowConfidence)).toBeInTheDocument();
    });

    it("clears the selection when the article was not in force on the date", () => {
        setup();
        ask("2001-01-01");
        expect(screen.queryByText(/Seçili sürüm/)).not.toBeInTheDocument();
    });

    it("says the article was not in force before it existed, and warns about a date after the newest copy", () => {
        setup();
        ask("2001-01-01");
        expect(answer()).toHaveTextContent(dateQuery.notInForce);
        ask("2027-01-01");
        expect(answer()).toHaveTextContent("Tarih son kopyadan (22.04.2026) sonra");
    });

    it("asks for a date first", () => {
        setup();
        expect(answer()).toHaveTextContent(dateQuery.hint);
    });

    it("explains the timeline, its change kinds, the gap and the date query in tips", async () => {
        setup();
        const { help } = messages.review.statutes;
        const tips = [
            [texts.title, help.timeline],
            [texts.kindsTopic, help.timelineKinds],
            [texts.gap, help.gap],
            [dateQuery.title, help.dateQuery],
        ] as const;
        for (const [topic, text] of tips) {
            await userEvent.click(infoTip(topic));
            expect(openTipText()).toHaveTextContent(text);
        }
    });

    it("explains the parts of the selected version, but not inside the version buttons", async () => {
        setup();
        fireEvent.click(screen.getAllByRole("button", { name: /11.09.2014/ })[0] as HTMLElement);
        const { help } = messages.review.statutes;
        const parts = [
            [version.footnotes, help.versionFootnotes],
            [version.evidence, help.versionEvidence],
            [version.amendments, help.versionAmendments],
            [version.copies, help.versionCopies],
            [version.diff, help.diff],
        ] as const;
        for (const [topic, text] of parts) {
            await userEvent.click(within(panel()).getByRole("button", { name: `Bilgi: ${topic}` }));
            expect(openTipText()).toHaveTextContent(text);
        }
        for (const button of screen.getAllByRole("button", { name: /\d{2}\.\d{2}\.\d{4}/ })) {
            expect(within(button).queryByRole("button")).toBeNull();
        }
    });
});
