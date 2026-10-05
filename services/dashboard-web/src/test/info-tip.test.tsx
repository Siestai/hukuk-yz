import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InfoTip } from "@hukuk/ui";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const label = "Bilgi: Güven dağılımı";
const text = "Programın bir kaydı ne kadar güvenle okuduğu.";

const view = () => (
    <>
        <InfoTip label={label}>{text}</InfoTip>
        <button>dışarısı</button>
    </>
);
const button = () => screen.getByRole("button", { name: label });
const box = () => document.querySelector('[data-slot="info-tip-content"]');

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => vi.useRealTimers());

describe("InfoTip", () => {
    it("is a closed button named after its topic", () => {
        render(view());
        expect(button()).toHaveAttribute("aria-expanded", "false");
        expect(box()).toBeNull();
    });

    it("shows the box while the mouse is over the button and hides it after a moment", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.hover(button());
        expect(button()).toHaveAttribute("aria-expanded", "true");
        expect(box()).toHaveTextContent(text);
        await user.unhover(button());
        expect(box()).not.toBeNull();
        act(() => vi.advanceTimersByTime(200));
        expect(box()).toBeNull();
        expect(button()).toHaveAttribute("aria-expanded", "false");
    });

    it("stays open while the pointer moves from the button onto the box", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.hover(button());
        await user.unhover(button());
        await user.hover(box() as Element);
        act(() => vi.advanceTimersByTime(500));
        expect(box()).not.toBeNull();
    });

    it("ignores the hover of a finger and opens on the tap", () => {
        render(view());
        fireEvent.pointerEnter(button(), { pointerType: "touch" });
        expect(box()).toBeNull();
        fireEvent.click(button());
        expect(button()).toHaveAttribute("aria-expanded", "true");
        expect(box()).toHaveTextContent(text);
    });

    it("opens on keyboard focus and closes when focus leaves", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.tab();
        expect(button()).toHaveFocus();
        expect(box()).toHaveTextContent(text);
        await user.tab();
        expect(box()).toBeNull();
    });

    it("pins on click: the pointer leaving does not close it, a second click does", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.click(button());
        await user.unhover(button());
        act(() => vi.advanceTimersByTime(500));
        expect(box()).not.toBeNull();
        await user.click(button());
        expect(box()).toBeNull();
    });

    it("closes on Escape and keeps the focus on the button", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.click(button());
        await user.keyboard("{Escape}");
        expect(box()).toBeNull();
        expect(button()).toHaveFocus();
        expect(button()).toHaveAttribute("aria-expanded", "false");
    });

    it("closes on a press outside", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.click(button());
        await user.click(screen.getByRole("button", { name: "dışarısı" }));
        expect(box()).toBeNull();
    });

    it("keeps the focus on the button when it opens", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.click(button());
        expect(button()).toHaveFocus();
    });

    it("reads the text out through a status region only once activated", async () => {
        const user = userEvent.setup({ delay: null, advanceTimers: vi.advanceTimersByTime });
        render(view());
        await user.tab();
        expect(screen.getByRole("status")).toBeEmptyDOMElement();
        await user.keyboard("{Enter}");
        expect(screen.getByRole("status")).toHaveTextContent(text);
        // The visible box is hidden from assistive technology; the region speaks for it.
        expect(box()).toHaveAttribute("aria-hidden", "true");
    });

    it("gives a touch screen a 44 px target without growing the icon", () => {
        render(view());
        expect(button()).toHaveClass("pointer-coarse:size-11", "pointer-coarse:-m-3", "size-5");
    });
});
