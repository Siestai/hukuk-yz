import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { AppShell } from "./app-shell";

vi.mock("next/navigation", () => ({
    useRouter: () => ({ replace: vi.fn() }),
    usePathname: () => "/",
}));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST: vi.fn() }) }));

const user = { display_name: "Baran Yılmaz", role: "reviewer" } as const;

describe("AppShell", () => {
    it("has the side navigation, the mobile bar and the page", () => {
        renderWithIntl(
            <AppShell user={user} pending={3}>
                <p>içerik</p>
            </AppShell>,
        );
        // Both are in the DOM; CSS shows the side navigation from `lg` up and the bar below.
        const side = screen.getByRole("complementary");
        expect(side).toHaveClass("hidden", "lg:flex");
        expect(
            within(side).getByRole("navigation", { name: messages.nav.label }),
        ).toBeInTheDocument();
        expect(within(side).getByText("Baran Yılmaz")).toBeInTheDocument();
        const bar = screen.getByRole("banner");
        expect(bar).toHaveClass("lg:hidden", "sticky");
        expect(within(bar).getByRole("button", { name: messages.nav.menu })).toBeInTheDocument();
        expect(screen.getByText("içerik")).toBeInTheDocument();
    });
});

describe("AppShell help", () => {
    it("has tips on the pending count and on the sections that are not ready", () => {
        renderWithIntl(
            <AppShell user={user} pending={3}>
                <p>içerik</p>
            </AppShell>,
        );
        const side = within(screen.getByRole("complementary"));
        for (const topic of [
            messages.nav.pending,
            messages.nav.sources,
            messages.nav.knowledgeBase,
        ]) {
            expect(
                side.getByRole("button", {
                    name: messages.review.queue.help.label.replace("{topic}", topic),
                }),
            ).toBeInTheDocument();
        }
    });

    it("keeps the tips out of the navigation link", () => {
        renderWithIntl(
            <AppShell user={user} pending={3}>
                <p>içerik</p>
            </AppShell>,
        );
        const side = within(screen.getByRole("complementary"));
        expect(
            within(side.getByRole("link", { name: new RegExp(messages.nav.queue) })).queryByRole(
                "button",
            ),
        ).toBeNull();
    });
});
