import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { usePhone } from "./use-phone";

/** A `matchMedia` for the phone query that the test can flip, like a resized window. */
function mockPhoneQuery(initial: boolean) {
    const original = window.matchMedia;
    let matches = initial;
    const listeners = new Set<() => void>();
    window.matchMedia = vi.fn((query: string) => ({
        get matches() {
            return matches;
        },
        media: query,
        addEventListener: (_: string, listener: () => void) => listeners.add(listener),
        removeEventListener: (_: string, listener: () => void) => listeners.delete(listener),
    })) as unknown as typeof window.matchMedia;
    return {
        listeners,
        set: (value: boolean) =>
            act(() => {
                matches = value;
                listeners.forEach((listener) => listener());
            }),
        restore: () => {
            window.matchMedia = original;
        },
    };
}

describe("usePhone", () => {
    let restore = () => {};
    afterEach(() => restore());

    it("asks for the screens narrower than md and follows the window", () => {
        const media = mockPhoneQuery(true);
        restore = media.restore;
        const { result } = renderHook(usePhone);
        expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 767.98px)");
        expect(result.current).toBe(true);
        media.set(false);
        expect(result.current).toBe(false);
    });

    it("stops listening when unmounted", () => {
        const media = mockPhoneQuery(false);
        restore = media.restore;
        const { unmount } = renderHook(usePhone);
        expect(media.listeners.size).toBe(1);
        unmount();
        expect(media.listeners.size).toBe(0);
    });
});
