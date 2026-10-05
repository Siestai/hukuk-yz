import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Dialog } from "@hukuk/ui";
import { useRef, useState } from "react";
import { describe, expect, it, vi } from "vitest";

function Harness({ dismissible = true, onClose }: { dismissible?: boolean; onClose?: () => void }) {
    const [open, setOpen] = useState(false);
    const target = useRef<HTMLButtonElement>(null);
    return (
        <>
            <button onClick={() => setOpen(true)}>open</button>
            <button ref={target}>target</button>
            <Dialog
                open={open}
                onClose={() => {
                    onClose?.();
                    setOpen(false);
                }}
                title="Başlık"
                dismissible={dismissible}
                returnFocusTo={target}
            >
                <input aria-label="inside" />
            </Dialog>
        </>
    );
}

const escape = () => new Event("cancel", { cancelable: true });

describe("Dialog", () => {
    it("is a labelled modal dialog whose content exists only while open", async () => {
        render(<Harness />);
        expect(screen.queryByLabelText("inside")).not.toBeInTheDocument();
        await userEvent.click(screen.getByText("open"));
        const dialog = screen.getByRole("dialog", { name: "Başlık" });
        expect(dialog).toContainElement(screen.getByLabelText("inside"));
    });

    it("asks to close once on Escape, and keeps the browser from closing it itself", async () => {
        const onClose = vi.fn();
        render(<Harness onClose={onClose} />);
        await userEvent.click(screen.getByText("open"));
        const event = escape();
        screen.getByRole("dialog").dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it("ignores Escape while it is not dismissible", async () => {
        const onClose = vi.fn();
        render(<Harness dismissible={false} onClose={onClose} />);
        await userEvent.click(screen.getByText("open"));
        const event = escape();
        screen.getByRole("dialog").dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
        expect(onClose).not.toHaveBeenCalled();
        expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    it("returns the focus to the element given, else to the element that opened it", async () => {
        render(<Harness />);
        await userEvent.click(screen.getByText("open"));
        screen.getByRole("dialog").dispatchEvent(escape());
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(screen.getByText("target")).toHaveFocus();
    });
});

describe("Dialog without a target", () => {
    it("returns the focus to the element that opened it", async () => {
        function Plain() {
            const [open, setOpen] = useState(false);
            return (
                <>
                    <button onClick={() => setOpen(true)}>open</button>
                    <Dialog open={open} onClose={() => setOpen(false)} title="Başlık">
                        x
                    </Dialog>
                </>
            );
        }
        render(<Plain />);
        const opener = screen.getByText("open");
        opener.focus();
        await userEvent.click(opener);
        screen.getByRole("dialog").dispatchEvent(escape());
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(opener).toHaveFocus();
    });
});

describe("Dialog drawer variant", () => {
    function Drawer({ onClose }: { onClose?: () => void }) {
        const [open, setOpen] = useState(false);
        const opener = useRef<HTMLButtonElement>(null);
        return (
            <>
                <button ref={opener} onClick={() => setOpen(true)}>
                    open
                </button>
                <Dialog
                    open={open}
                    variant="drawer"
                    closeLabel="Kapat"
                    returnFocusTo={opener}
                    onClose={() => {
                        onClose?.();
                        setOpen(false);
                    }}
                    title="Menü"
                >
                    <button>içerik</button>
                </Dialog>
            </>
        );
    }

    it("sticks to the left edge at full height and keeps the modal behaviour", async () => {
        const onClose = vi.fn();
        render(<Drawer onClose={onClose} />);
        await userEvent.click(screen.getByText("open"));
        const dialog = screen.getByRole("dialog", { name: "Menü" });
        expect(dialog).toHaveClass("mr-auto", "h-viewport", "overscroll-contain");
        expect(dialog).not.toHaveClass("m-auto");
        const event = escape();
        dialog.dispatchEvent(event);
        expect(event.defaultPrevented).toBe(true);
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(onClose).toHaveBeenCalledTimes(1);
        expect(screen.getByText("open")).toHaveFocus();
    });

    it("closes on a click on the backdrop, not on a click inside", async () => {
        const onClose = vi.fn();
        render(<Drawer onClose={onClose} />);
        await userEvent.click(screen.getByText("open"));
        await userEvent.click(screen.getByText("içerik"));
        expect(onClose).not.toHaveBeenCalled();
        // The backdrop is part of the dialog element: a click there targets the element itself.
        await userEvent.click(screen.getByRole("dialog"));
        expect(onClose).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("ignores the backdrop while it is not dismissible", async () => {
        const onClose = vi.fn();
        render(
            <Dialog open variant="drawer" dismissible={false} onClose={onClose} title="Menü">
                x
            </Dialog>,
        );
        await userEvent.click(screen.getByRole("dialog"));
        expect(onClose).not.toHaveBeenCalled();
    });

    it("has a close button that asks to close", async () => {
        const onClose = vi.fn();
        render(<Drawer onClose={onClose} />);
        await userEvent.click(screen.getByText("open"));
        await userEvent.click(screen.getByRole("button", { name: "Kapat" }));
        expect(onClose).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
});

describe("Dialog (center variant)", () => {
    it("is a bounded, scrollable box inset from the screen edges", async () => {
        render(<Harness />);
        await userEvent.click(screen.getByText("open"));
        const dialog = screen.getByRole("dialog");
        expect(dialog).toHaveClass(
            "w-inset",
            "max-h-inset",
            "overflow-y-auto",
            "overscroll-contain",
        );
    });
});
