import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { MobileNav } from "./mobile-nav";

const pathname = vi.hoisted(() => vi.fn(() => "/"));
vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: vi.fn() }),
    usePathname: pathname,
}));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST: vi.fn() }) }));

const user = { display_name: "Baran Yılmaz", role: "reviewer" } as const;
const escape = () => new Event("cancel", { cancelable: true });

function setup(pending: number | null = 1207) {
    renderWithIntl(<MobileNav user={user} pending={pending} />);
    return {
        menu: screen.getByRole("button", { name: messages.nav.menu }),
        events: userEvent.setup(),
    };
}

/** A `matchMedia` whose `(min-width: 1024px)` query the test can flip, like a resized window. */
function mockWideQuery() {
    const listeners = new Set<(event: MediaQueryListEvent) => void>();
    const original = window.matchMedia;
    window.matchMedia = vi.fn((query: string) => ({
        matches: false,
        media: query,
        addEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
            listeners.add(listener),
        removeEventListener: (_: string, listener: (event: MediaQueryListEvent) => void) =>
            listeners.delete(listener),
    })) as unknown as typeof window.matchMedia;
    return {
        listeners,
        change: (matches: boolean) =>
            act(() =>
                listeners.forEach((listener) => listener({ matches } as MediaQueryListEvent)),
            ),
        restore: () => {
            window.matchMedia = original;
        },
    };
}

describe("MobileNav", () => {
    it("shows the brand, the pending count and a closed menu button", () => {
        const { menu } = setup();
        expect(screen.getByRole("img", { name: messages.brand.logoLabel })).toBeInTheDocument();
        expect(screen.getByText("1.207")).toBeInTheDocument();
        expect(menu).toHaveAttribute("aria-expanded", "false");
        expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("shows no count when it could not be fetched", () => {
        setup(null);
        expect(screen.queryByText(messages.nav.pending)).toBeNull();
    });

    it("opens the drawer with the links, the user and the logout button", async () => {
        const { menu, events } = setup();
        await events.click(menu);
        const drawer = screen.getByRole("dialog", { name: messages.nav.menu });
        expect(menu).toHaveAttribute("aria-expanded", "true");
        expect(menu).toHaveAttribute("aria-controls", drawer.id);
        expect(
            within(drawer).getByRole("link", { name: new RegExp(messages.nav.queue) }),
        ).toHaveAttribute("href", "/");
        expect(within(drawer).getByText("Baran Yılmaz")).toBeInTheDocument();
        expect(
            within(drawer).getByRole("button", { name: messages.nav.logout }),
        ).toBeInTheDocument();
    });

    it("closes on Escape and gives the focus back to the menu button", async () => {
        const { menu, events } = setup();
        await events.click(menu);
        screen.getByRole("dialog").dispatchEvent(escape());
        await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
        expect(menu).toHaveAttribute("aria-expanded", "false");
        expect(menu).toHaveFocus();
    });

    it("closes with its close button", async () => {
        const { menu, events } = setup();
        await events.click(menu);
        await events.click(screen.getByRole("button", { name: messages.nav.closeMenu }));
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(menu).toHaveFocus();
    });

    it("closes when a link is followed", async () => {
        const { menu, events } = setup();
        await events.click(menu);
        await events.click(screen.getByRole("link", { name: new RegExp(messages.nav.queue) }));
        expect(screen.queryByRole("dialog")).toBeNull();
        expect(menu).toHaveFocus();
    });

    describe("when the screen grows to lg", () => {
        let query: ReturnType<typeof mockWideQuery>;
        beforeEach(() => {
            query = mockWideQuery();
        });
        afterEach(() => query.restore());

        it("closes the open drawer, and ignores a change back to a narrow screen", async () => {
            const { menu, events } = setup();
            expect(window.matchMedia).toHaveBeenCalledWith("(min-width: 1024px)");
            await events.click(menu);
            query.change(false);
            expect(screen.getByRole("dialog")).toBeInTheDocument();
            query.change(true);
            expect(screen.queryByRole("dialog")).toBeNull();
            expect(menu).toHaveAttribute("aria-expanded", "false");
        });

        it("stops listening when it unmounts", () => {
            const { unmount } = renderWithIntl(<MobileNav user={user} pending={null} />);
            expect(query.listeners.size).toBe(1);
            unmount();
            expect(query.listeners.size).toBe(0);
        });
    });
});
