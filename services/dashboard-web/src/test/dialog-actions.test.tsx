import { render, screen } from "@testing-library/react";
import { DialogActions } from "@hukuk/ui";
import { describe, expect, it } from "vitest";

describe("DialogActions", () => {
    it("stacks full-width buttons with the main action on top on a phone, one row from md up", () => {
        render(
            <DialogActions>
                <button>İptal</button>
                <button>Tamam</button>
            </DialogActions>,
        );
        const row = screen.getByText("İptal").parentElement;
        expect(row).toHaveClass(
            "flex-col-reverse",
            "*:w-full",
            "md:flex-row",
            "md:justify-end",
            "md:*:w-auto",
        );
        // The DOM order, which is the tab order, stays cancel then main action.
        expect([...(row?.children ?? [])].map((child) => child.textContent)).toEqual([
            "İptal",
            "Tamam",
        ]);
    });
});
