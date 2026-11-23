import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CaseFacts } from "@/lib/chat-types";
import { renderWithIntl } from "@/test/intl";
import { FactsCard } from "./facts-card";

const facts = {
    facts: [
        { key: "kidem", label: "Kıdem", value: "5 ay", status: "known" },
        { key: "isci", label: "İşçi sayısı", value: null, status: "unknown" },
    ],
} as unknown as CaseFacts;

describe("FactsCard", () => {
    it("marks what is not known", () => {
        renderWithIntl(<FactsCard facts={facts} />);
        expect(screen.getByText("Anladığım olay")).toBeInTheDocument();
        expect(screen.getByText("Bilinmiyor")).toBeInTheDocument();
        expect(screen.getByText("5 ay")).toBeInTheDocument();
    });

    it("shows an ISO date as DD.MM.YYYY and leaves other values as they are", () => {
        const dated = {
            facts: [
                { key: "tutanak", label: "Tutanak", value: "2026-10-03", status: "known" },
                { key: "kidem", label: "Kıdem", value: "2026-13-45 ay", status: "known" },
            ],
        } as unknown as CaseFacts;
        renderWithIntl(<FactsCard facts={dated} />);
        expect(screen.getByText("03.10.2026")).toBeInTheDocument();
        expect(screen.getByText("2026-13-45 ay")).toBeInTheDocument();
    });

    it("sends a corrected value as a new message", async () => {
        const onCorrect = vi.fn();
        renderWithIntl(<FactsCard facts={facts} onCorrect={onCorrect} />);
        await userEvent.click(screen.getByText("5 ay"));
        const input = screen.getByLabelText("Kıdem değerini düzelt");
        await userEvent.clear(input);
        await userEvent.type(input, "8 ay");
        await userEvent.click(screen.getByRole("button", { name: "Düzelt" }));
        expect(onCorrect).toHaveBeenCalledWith("Kıdem yanlış anlaşılmış, doğrusu: 8 ay");
    });
});
