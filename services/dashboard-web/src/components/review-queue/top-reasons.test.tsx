import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { parseQueueParams } from "@/lib/queue-params";
import { TopReasons } from "./top-reasons";

const reasons = Object.keys(messages.enums.reason)
    .slice(0, 7)
    .map((reason, i) => ({ reason, count: 2000 - i }));

const view = (list = reasons, search = "") => (
    <TopReasons reasons={list} params={parseQueueParams(new URLSearchParams(search))} />
);

describe("TopReasons", () => {
    it("lists the first five reasons with labels and counts", () => {
        renderWithIntl(view());
        const links = screen.getAllByRole("link");
        expect(links).toHaveLength(5);
        expect(links[0]).toHaveTextContent(`${messages.enums.reason.missing_court}2.000`);
    });

    it("links to the reason filter on page 1", () => {
        renderWithIntl(view(reasons, "page=2"));
        expect(screen.getByRole("link", { name: /Esas no yok/ })).toHaveAttribute(
            "href",
            "/?reason=missing_esas_no",
        );
    });

    it("marks the active reason and links it to its own removal", () => {
        renderWithIntl(view(reasons, "reason=missing_esas_no"));
        const link = screen.getByRole("link", { name: /Esas no yok/ });
        expect(link).toHaveAttribute("aria-current", "true");
        expect(link).toHaveAttribute("href", "/");
    });

    it("says so when there are no reasons", () => {
        renderWithIntl(view([]));
        expect(screen.getByText(messages.review.queue.summary.noReasons)).toBeInTheDocument();
    });
});

describe("TopReasons help", () => {
    it("has a tip on the title and one on every reason it shows", () => {
        renderWithIntl(view());
        expect(infoTip(messages.review.queue.summary.topReasons)).toBeInTheDocument();
        for (const { reason } of reasons.slice(0, 5)) {
            expect(
                infoTip(messages.enums.reason[reason as keyof typeof messages.enums.reason]),
            ).toBeInTheDocument();
        }
        expect(screen.getAllByRole("button")).toHaveLength(6);
    });

    it("says what the reason means and what to check", async () => {
        renderWithIntl(view());
        await userEvent.click(infoTip(messages.enums.reason.missing_esas_no));
        expect(openTipText()).toHaveTextContent(messages.review.queue.help.reason.missing_esas_no);
    });

    it("keeps the tip out of the reason link", () => {
        renderWithIntl(view());
        for (const link of screen.getAllByRole("link")) {
            expect(within(link).queryByRole("button")).toBeNull();
        }
    });
});
