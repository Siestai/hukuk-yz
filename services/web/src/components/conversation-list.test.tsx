import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Conversation } from "@/lib/chat-types";
import { renderWithIntl } from "@/test/intl";
import { ConversationList } from "./conversation-list";

vi.mock("@hukuk/web-core/components/logout-button", () => ({ LogoutButton: () => null }));

function conversation(id: string, title: string, pinned = false): Conversation {
    return {
        id,
        durable_delivery: false,
        title,
        pinned,
        created_at: "2026-10-01T12:00:00Z",
        updated_at: "2026-10-01T12:00:00Z",
    };
}

function renderList(
    conversations: Conversation[],
    extra: { notice?: string; onPin?: () => void } = {},
) {
    return renderWithIntl(
        <ConversationList
            conversations={conversations}
            activeId="c1"
            onNew={vi.fn()}
            onPin={extra.onPin ?? vi.fn()}
            notice={extra.notice ?? null}
            onNavigate={vi.fn()}
        />,
    );
}

describe("ConversationList", () => {
    it("marks the active conversation and closes the drawer on a new question", async () => {
        const onNew = vi.fn();
        const onNavigate = vi.fn();
        renderWithIntl(
            <ConversationList
                conversations={[conversation("c1", "İşe iade")]}
                activeId="c1"
                onNew={onNew}
                onPin={vi.fn()}
                notice={null}
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

    it("shows only 'Konuşmalar' without pins, and 'Sabitlenenler' above it with pins", () => {
        const { unmount } = renderList([conversation("c1", "İşe iade")]);
        expect(screen.queryByText("Sabitlenenler")).toBeNull();
        expect(screen.getByText("Konuşmalar")).toBeInTheDocument();
        unmount();

        renderList([conversation("c2", "Fesih", true), conversation("c1", "İşe iade")]);
        const pinned = screen.getByRole("region", { name: "Sabitlenenler" });
        const rest = screen.getByRole("region", { name: "Konuşmalar" });
        expect(within(pinned).getByRole("link", { name: /Fesih/ })).toBeInTheDocument();
        expect(within(rest).getByRole("link", { name: /İşe iade/ })).toBeInTheDocument();
    });

    it("pins and unpins with an icon button that has a name", async () => {
        const onPin = vi.fn();
        renderList([conversation("c2", "Fesih", true), conversation("c1", "İşe iade")], { onPin });
        await userEvent.click(screen.getByRole("button", { name: "Sabitle: İşe iade" }));
        expect(onPin).toHaveBeenLastCalledWith("c1", true);
        await userEvent.click(screen.getByRole("button", { name: "Sabitlemeyi kaldır: Fesih" }));
        expect(onPin).toHaveBeenLastCalledWith("c2", false);
    });

    it("truncates a long title to one line and keeps the full text in the title attribute", () => {
        const long = "Kamu görevlisinin ölüm toptan ödemesi ve sonrası";
        renderList([conversation("c1", long)]);
        const text = screen.getByText(long);
        expect(text).toHaveAttribute("title", long);
        expect(text).toHaveClass("truncate");
    });

    it("shows the notice of a refused pin", () => {
        renderList([conversation("c1", "İşe iade")], {
            notice: "En fazla 3 konuşma sabitlenebilir.",
        });
        expect(screen.getByRole("status")).toHaveTextContent("En fazla 3 konuşma sabitlenebilir.");
    });
});
