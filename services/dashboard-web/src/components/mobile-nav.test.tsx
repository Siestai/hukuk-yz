import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
});
