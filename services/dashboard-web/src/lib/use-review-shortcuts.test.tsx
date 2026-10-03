import { fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useReviewShortcuts, type Shortcut } from "./use-review-shortcuts";

function Harness({ enabled = true, calls }: { enabled?: boolean; calls: (s: Shortcut) => void }) {
    useReviewShortcuts(
        {
            approve: () => calls("approve"),
            edit: () => calls("edit"),
            reject: () => calls("reject"),
            next: () => calls("next"),
            previous: () => calls("previous"),
        },
        enabled,
    );
    return (
        <div>
            <input aria-label="field" />
            <textarea aria-label="area" />
            <select aria-label="choice" />
            <div contentEditable suppressContentEditableWarning aria-label="rich" />
            <button>button</button>
        </div>
    );
}

afterEach(() => {
    document.querySelectorAll("dialog").forEach((dialog) => dialog.remove());
});

describe("useReviewShortcuts", () => {
    it.each([
        ["a", "approve"],
        ["e", "edit"],
        ["r", "reject"],
        ["j", "next"],
        ["k", "previous"],
        ["A", "approve"],
    ])("%s runs %s", (key, expected) => {
        const calls = vi.fn();
        render(<Harness calls={calls} />);
        fireEvent.keyDown(document.body, { key });
        expect(calls).toHaveBeenCalledExactlyOnceWith(expected);
    });

    it("ignores other keys and held-down repeats", () => {
        const calls = vi.fn();
        render(<Harness calls={calls} />);
        fireEvent.keyDown(document.body, { key: "x" });
        fireEvent.keyDown(document.body, { key: "a", repeat: true });
        expect(calls).not.toHaveBeenCalled();
    });

    it.each(["field", "area", "choice", "rich"])("ignores typing in the %s", (label) => {
        const calls = vi.fn();
        const { getByLabelText } = render(<Harness calls={calls} />);
        fireEvent.keyDown(getByLabelText(label), { key: "a" });
        expect(calls).not.toHaveBeenCalled();
    });

    it.each(["ctrlKey", "metaKey", "altKey", "shiftKey"])("ignores a press with %s", (modifier) => {
        const calls = vi.fn();
        render(<Harness calls={calls} />);
        fireEvent.keyDown(document.body, { key: "a", [modifier]: true });
        expect(calls).not.toHaveBeenCalled();
    });

    it("ignores everything while a dialog is open", () => {
        const calls = vi.fn();
        render(<Harness calls={calls} />);
        const dialog = document.createElement("dialog");
        dialog.setAttribute("open", "");
        document.body.append(dialog);
        fireEvent.keyDown(document.body, { key: "a" });
        expect(calls).not.toHaveBeenCalled();
    });

    it("does nothing while disabled (a request runs)", () => {
        const calls = vi.fn();
        const { rerender } = render(<Harness calls={calls} enabled={false} />);
        fireEvent.keyDown(document.body, { key: "a" });
        expect(calls).not.toHaveBeenCalled();
        rerender(<Harness calls={calls} />);
        fireEvent.keyDown(document.body, { key: "a" });
        expect(calls).toHaveBeenCalledTimes(1);
    });

    it("works from a focused button", () => {
        const calls = vi.fn();
        const { getByText } = render(<Harness calls={calls} />);
        fireEvent.keyDown(getByText("button"), { key: "j" });
        expect(calls).toHaveBeenCalledExactlyOnceWith("next");
    });
});
