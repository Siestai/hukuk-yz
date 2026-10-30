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
