import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";
import { Composer } from "./composer";

function setup(disabled = false) {
    const onSend = vi.fn();
    renderWithIntl(<Composer disabled={disabled} onSend={onSend} />);
    return { onSend, box: screen.getByRole("textbox", { name: "Sorunuz" }) };
}

describe("Composer", () => {
    it("sends the trimmed text on Enter and clears the box", async () => {
        const { onSend, box } = setup();
        await userEvent.type(box, "  Kıdem tazminatı?  {Enter}");
        expect(onSend).toHaveBeenCalledExactlyOnceWith("Kıdem tazminatı?");
        expect(box).toHaveValue("");
    });

    it("starts a new line on Shift+Enter instead of sending", async () => {
        const { onSend, box } = setup();
        await userEvent.type(box, "bir{Shift>}{Enter}{/Shift}iki");
        expect(onSend).not.toHaveBeenCalled();
        expect(box).toHaveValue("bir\niki");
    });

    it("sends nothing for blank text", async () => {
        const { onSend, box } = setup();
        await userEvent.type(box, "   {Enter}");
        expect(onSend).not.toHaveBeenCalled();
        expect(screen.getByRole("button", { name: "Gönder" })).toBeDisabled();
    });

    it("sends nothing while an answer is coming", async () => {
        const { onSend, box } = setup(true);
        await userEvent.type(box, "soru{Enter}");
        expect(onSend).not.toHaveBeenCalled();
        expect(screen.getByRole("button", { name: "Gönder" })).toBeDisabled();
    });
});
