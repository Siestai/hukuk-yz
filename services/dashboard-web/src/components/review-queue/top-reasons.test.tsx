import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
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
