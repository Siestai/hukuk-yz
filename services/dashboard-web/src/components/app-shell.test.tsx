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
