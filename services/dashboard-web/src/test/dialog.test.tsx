import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dialog } from "@hukuk/ui";
import { useState } from "react";
import { describe, expect, it } from "vitest";

function Harness() {
    const [open, setOpen] = useState(false);
    return (
        <>
            <button onClick={() => setOpen(true)}>open</button>
            <Dialog open={open} onClose={() => setOpen(false)} title="Başlık">
                <input aria-label="inside" />
            </Dialog>
        </>
    );
}

describe("Dialog", () => {
    it("is a labelled modal dialog whose content exists only while open", async () => {
        render(<Harness />);
        expect(screen.queryByLabelText("inside")).not.toBeInTheDocument();
        await userEvent.click(screen.getByText("open"));
        const dialog = screen.getByRole("dialog", { name: "Başlık" });
        expect(dialog).toHaveAttribute("aria-modal", "true");
        expect(dialog).toContainElement(screen.getByLabelText("inside"));
    });

    it("returns the focus to the element that opened it", async () => {
        render(<Harness />);
        const opener = screen.getByText("open");
        opener.focus();
        await userEvent.click(opener);
        screen.getByRole("dialog").dispatchEvent(new Event("close"));
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(opener).toHaveFocus();
    });
});
