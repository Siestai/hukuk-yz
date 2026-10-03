import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { DocumentTabs } from "./document-tabs";

beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, body: null }));
});

function setup() {
    renderWithIntl(
        <DocumentTabs pdfSrc="/api/review/decisions/d1/file" text={<p>karar metni</p>} />,
    );
    return {
        pdf: screen.getByRole("tab", { name: messages.review.detail.tabPdf }),
        text: screen.getByRole("tab", { name: messages.review.detail.tabText }),
    };
}

describe("DocumentTabs", () => {
    it("is an accessible tablist with the PDF selected first", () => {
        const { pdf, text } = setup();
        expect(screen.getByRole("tablist")).toBeInTheDocument();
        expect(pdf).toHaveAttribute("aria-selected", "true");
        expect(text).toHaveAttribute("aria-selected", "false");
        expect(pdf).toHaveAttribute("tabindex", "0");
        expect(text).toHaveAttribute("tabindex", "-1");
        const panel = screen.getByRole("tabpanel");
        expect(panel).toHaveAttribute("aria-labelledby", pdf.id);
        expect(pdf).toHaveAttribute("aria-controls", panel.id);
    });

    it("switches panels on click", async () => {
        const { text } = setup();
        await userEvent.click(text);
        expect(screen.getByRole("tabpanel")).toHaveTextContent("karar metni");
        expect(screen.getByRole("tabpanel")).toHaveAttribute("aria-labelledby", text.id);
    });

    it("moves with the arrow keys, wrapping, and with Home and End", async () => {
        const { pdf, text } = setup();
        pdf.focus();
        await userEvent.keyboard("{ArrowRight}");
        expect(text).toHaveFocus();
        expect(text).toHaveAttribute("aria-selected", "true");
        await userEvent.keyboard("{ArrowRight}");
        expect(pdf).toHaveFocus();
        await userEvent.keyboard("{ArrowLeft}");
        expect(text).toHaveFocus();
        await userEvent.keyboard("{Home}");
        expect(pdf).toHaveFocus();
        await userEvent.keyboard("{End}");
        expect(text).toHaveFocus();
        expect(text).toHaveAttribute("aria-selected", "true");
    });

    it("keeps the PDF mounted while the text tab is shown", async () => {
        const { text } = setup();
        await userEvent.click(text);
        expect(await screen.findByTitle(messages.review.detail.pdf.title)).toBeInTheDocument();
    });
});
