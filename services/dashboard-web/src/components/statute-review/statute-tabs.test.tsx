import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { messages } from "@/i18n/messages";
import { QueueTabs } from "@/components/review-queue/queue-tabs";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { StatuteTabs } from "./statute-tabs";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const params: StatuteQueueParams = { kind: "statute", statute: "5510", band: "low", page: 3 };
const { statuteTabs } = messages.review.statutes;

describe("StatuteTabs", () => {
    it("links each statute to its first page, keeping the filters, and marks the open one", () => {
        renderWithIntl(<StatuteTabs params={params} waiting={{ "4857": 40, "5510": 11 }} />);
        const nav = within(screen.getByRole("navigation", { name: statuteTabs.label }));
        const first = nav.getByRole("link", { name: /4857 İş Kanunu/ });
        expect(first).toHaveAttribute("href", "/mevzuat?band=low");
        expect(first).toHaveTextContent("40");
        const open = nav.getByRole("link", { name: /5510 SGK Kanunu/ });
        expect(open).toHaveAttribute("aria-current", "page");
        expect(open).toHaveAttribute("href", "/mevzuat?kanun=5510&band=low");
    });

    it("explains each statute in a tip beside its link, not inside it", async () => {
        renderWithIntl(<StatuteTabs params={params} waiting={{ "4857": 40, "5510": 11 }} />);
        const nav = within(screen.getByRole("navigation", { name: statuteTabs.label }));
        expect(nav.getAllByRole("link")).toHaveLength(2);
        await userEvent.click(infoTip(statuteTabs["4857"]));
        expect(openTipText()).toHaveTextContent(messages.review.statutes.help.lawTab4857);
        expect(infoTip(statuteTabs["5510"]).closest("a")).toBeNull();
    });
});

describe("QueueTabs on the statute queue", () => {
    it("links the status tabs to /mevzuat, keeps statute and filters, and explains them with the statute texts", async () => {
        renderWithIntl(
            <QueueTabs
                params={params}
                counts={{ pending: 11, approved: 4, rejected: 1, all: 16 }}
            />,
        );
        const nav = screen.getByRole("navigation", {
            name: messages.review.queue.tabs.labelStatute,
        });
        expect(within(nav).getByRole("link", { name: /Onaylanan/ })).toHaveAttribute(
            "href",
            "/mevzuat?durum=onaylanan&kanun=5510&band=low",
        );
        expect(within(nav).getByRole("link", { name: /Bekleyen/ })).toHaveAttribute(
            "aria-current",
            "page",
        );
        const { pending, approved, rejected, all } = messages.review.queue.tabs;
        for (const label of [pending, approved, rejected, all]) {
            expect(
                within(nav).getByRole("button", { name: `Bilgi: ${label}` }),
            ).toBeInTheDocument();
        }
        await userEvent.click(infoTip("Onaylanan"));
        expect(openTipText()).toHaveTextContent(messages.review.statutes.help.tabApproved);
    });
});
