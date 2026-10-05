import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, renderWithIntl } from "@/test/intl";
import { QueuePagination } from "./queue-pagination";

const { pagination } = messages.review.queue;
const base = { sort: "score_asc" as const, page: 1 };

describe("QueuePagination", () => {
    it("shows the range of the first page with Turkish separators", () => {
        renderWithIntl(<QueuePagination params={base} total={6317} />);
        expect(screen.getByText("1-50 / 6.317")).toBeInTheDocument();
    });

    it("shows a short last page", () => {
        renderWithIntl(<QueuePagination params={{ ...base, page: 127 }} total={6317} />);
        expect(screen.getByText("6.301-6.317 / 6.317")).toBeInTheDocument();
    });

    it("omits Previous on the first page and links Next", () => {
        renderWithIntl(<QueuePagination params={base} total={6317} />);
        expect(screen.queryByRole("link", { name: pagination.previous })).toBeNull();
        expect(screen.queryByText(pagination.previous)).toBeNull();
        expect(screen.getByRole("link", { name: pagination.next })).toHaveAttribute(
            "href",
            "/?page=2",
        );
    });

    it("omits Next on the last page", () => {
        renderWithIntl(<QueuePagination params={{ ...base, page: 127 }} total={6317} />);
        expect(screen.queryByRole("link", { name: pagination.next })).toBeNull();
        expect(screen.queryByText(pagination.next)).toBeNull();
        expect(screen.getByRole("link", { name: pagination.previous })).toHaveAttribute(
            "href",
            "/?page=126",
        );
    });

    it("keeps the filters in every link and drops page=1", () => {
        renderWithIntl(<QueuePagination params={{ ...base, band: "low", page: 2 }} total={310} />);
        expect(screen.getByRole("link", { name: pagination.previous })).toHaveAttribute(
            "href",
            "/?band=low",
        );
        expect(screen.getByRole("link", { name: "Sayfa 3" })).toHaveAttribute(
            "href",
            "/?band=low&page=3",
        );
    });

    it("compacts many pages with ellipses and marks the current one", () => {
        renderWithIntl(<QueuePagination params={{ ...base, page: 50 }} total={6317} />);
        const nav = screen.getByRole("navigation", { name: pagination.label });
        expect(nav).toHaveTextContent("Önceki1…495051…127Sonraki");
        expect(screen.getByRole("link", { name: "Sayfa 50" })).toHaveAttribute(
            "aria-current",
            "page",
        );
        expect(screen.getByRole("link", { name: "Sayfa 49" })).not.toHaveAttribute("aria-current");
    });

    it("shows the page of the page count for a phone and hides the page numbers there", () => {
        renderWithIntl(<QueuePagination params={{ ...base, page: 50 }} total={6317} />);
        expect(screen.getByText("50 / 127")).toHaveClass("md:hidden");
        expect(screen.getByRole("link", { name: "Sayfa 49" })).toHaveClass(
            "hidden",
            "md:inline-flex",
        );
        expect(screen.getByRole("link", { name: pagination.next })).not.toHaveClass("hidden");
    });
});

describe("QueuePagination help", () => {
    it("has a tip for the page range", () => {
        renderWithIntl(<QueuePagination params={base} total={6317} />);
        expect(infoTip(pagination.label)).toBeInTheDocument();
    });
});
