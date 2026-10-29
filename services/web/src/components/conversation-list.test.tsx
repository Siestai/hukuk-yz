import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";
import { ConversationList } from "./conversation-list";

vi.mock("@hukuk/web-core/components/logout-button", () => ({ LogoutButton: () => null }));

describe("ConversationList", () => {
    it("marks the active conversation and closes the drawer on a new question", async () => {
        const onNew = vi.fn();
        const onNavigate = vi.fn();
        renderWithIntl(
            <ConversationList
                conversations={[
                    {
                        id: "c1",
                        title: "İşe iade",
                        created_at: "2026-10-01T12:00:00Z",
                        updated_at: "2026-10-01T12:00:00Z",
                    },
                ]}
                activeId="c1"
                onNew={onNew}
                onNavigate={onNavigate}
            />,
        );
        const link = screen.getByRole("link", { name: /İşe iade/ });
        expect(link).toHaveAttribute("href", "/konusmalar/c1");
        expect(link).toHaveAttribute("aria-current", "page");
        await userEvent.click(screen.getByRole("button", { name: /Yeni soru/ }));
        expect(onNew).toHaveBeenCalledOnce();
        expect(onNavigate).toHaveBeenCalledOnce();
    });
});
