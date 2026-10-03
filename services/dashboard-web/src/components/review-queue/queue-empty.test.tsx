import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { QueueEmpty } from "./queue-empty";

const { empty, filters } = messages.review.queue;

describe("QueueEmpty", () => {
    it("says nothing is pending when no filter is set", () => {
        renderWithIntl(<QueueEmpty params={{ sort: "score_asc", page: 1 }} pastEnd={false} />);
        expect(screen.getByText(empty.none)).toBeInTheDocument();
        expect(screen.queryByRole("link")).toBeNull();
    });

    it("offers to clear the filters, keeping the sort", () => {
        renderWithIntl(
            <QueueEmpty params={{ band: "low", sort: "score_desc", page: 1 }} pastEnd={false} />,
        );
        expect(screen.getByText(empty.filtered)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: filters.clear })).toHaveAttribute(
            "href",
            "/?sort=score_desc",
        );
    });

    it("links back to the first page, keeping the filters, past the last page", () => {
        renderWithIntl(<QueueEmpty params={{ band: "low", sort: "score_asc", page: 7 }} pastEnd />);
        expect(screen.getByText(empty.pastEnd)).toBeInTheDocument();
        expect(screen.getByRole("link", { name: empty.firstPage })).toHaveAttribute(
            "href",
            "/?band=low",
        );
    });
});
