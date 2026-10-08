import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { timeline } from "@/test/statute-fixtures";
import { renderWithIntl } from "@/test/intl";
import { TimelineList } from "./timeline-list";

const { timeline: texts } = messages.review.statutes;

function setup(selected: number | null = 2, matched: number | null = null) {
    const onSelect = vi.fn();
    renderWithIntl(
        <TimelineList
            timeline={timeline}
            selected={selected}
            matched={matched}
            onSelect={onSelect}
        />,
    );
    return { onSelect, user: userEvent.setup() };
}

describe("TimelineList", () => {
    it("lists versions and gaps oldest first with their date ranges", () => {
        setup();
        const list = screen.getByRole("list", { name: texts.label });
        const items = within(list)
            .getAllByRole("listitem")
            .filter((item) => item.parentElement === list);
        expect(items).toHaveLength(3);
        expect(items[0]).toHaveTextContent("10.06.2003 → 11.09.2014");
        expect(items[1]).toHaveTextContent("11.09.2014 → 01.01.2018");
        expect(items[2]).toHaveTextContent("01.01.2018 → bugün");
    });

    it("words the amending act and the date it came into force", () => {
        setup();
        expect(screen.getByText("6552 sayılı Kanun, yürürlük 11.09.2014")).toBeInTheDocument();
        expect(screen.getByText("7036 sayılı Kanun, yürürlük 01.01.2018")).toBeInTheDocument();
    });

    it("shows a gap as such: no text, the reason in plain words and the known amendments", () => {
        setup();
        const gap = screen.getByText(texts.gapNoText).closest("div");
        expect(gap).toHaveClass("border-dashed");
        expect(within(gap as HTMLElement).getByText(texts.gap)).toBeInTheDocument();
        expect(
            within(gap as HTMLElement).getByText(
                messages.enums.statuteWarning.before_earliest_snapshot,
            ),
        ).toBeInTheDocument();
        expect(within(gap as HTMLElement).getByText(texts.knownAmendments)).toBeInTheDocument();
        expect(
            within(gap as HTMLElement).getByText(
                "6552 sayılı Kanun · kabul 10.09.2014 · Ek (cümle)",
            ),
        ).toBeInTheDocument();
        // No version text anywhere in the gap, and a gap is not something to select.
        expect(gap).not.toHaveTextContent("İşçi");
        expect(within(gap as HTMLElement).queryByRole("button")).not.toBeInTheDocument();
    });

    it("selects a version on click and marks the selected one", async () => {
        const { onSelect, user } = setup(2);
        const buttons = screen.getAllByRole("button");
        expect(buttons).toHaveLength(2);
        expect(buttons[1]).toHaveAttribute("aria-pressed", "true");
        expect(buttons[0]).toHaveAttribute("aria-pressed", "false");
        await user.click(buttons[0] as HTMLElement);
        expect(onSelect).toHaveBeenCalledWith(1);
    });

    it("marks the entry the queried date falls in", () => {
        setup(2, 0);
        expect(
            within(screen.getByText(texts.gapNoText).closest("div") as HTMLElement).getByText(
                texts.queried,
            ),
        ).toBeInTheDocument();
        expect(screen.getAllByText(texts.queried)).toHaveLength(1);
    });

    it("tells a lower-confidence version apart", () => {
        setup();
        expect(
            within(screen.getAllByRole("button")[0] as HTMLElement).getByText(
                messages.enums.band.medium,
            ),
        ).toBeInTheDocument();
    });
});
