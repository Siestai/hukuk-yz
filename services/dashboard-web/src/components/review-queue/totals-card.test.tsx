import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import userEvent from "@testing-library/user-event";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { TotalsCard } from "./totals-card";

describe("TotalsCard", () => {
    it("shows the approved and rejected counts with a tip on the title", () => {
        renderWithIntl(<TotalsCard approved={1200} rejected={3} />);
        expect(screen.getByText("1.200")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
        expect(infoTip(messages.review.queue.summary.totalsTitle)).toBeInTheDocument();
    });

    it("leads the counts to their tabs", () => {
        renderWithIntl(<TotalsCard approved={1200} rejected={3} />);
        const { approved, rejected } = messages.review.queue.summary;
        expect(screen.getByRole("link", { name: approved })).toHaveAttribute(
            "href",
            "/?durum=onaylanan",
        );
        expect(screen.getByRole("link", { name: rejected })).toHaveAttribute(
            "href",
            "/?durum=reddedilen",
        );
    });

    it("explains the counts with the statute text on the statute queue", async () => {
        renderWithIntl(
            <TotalsCard
                approved={4}
                rejected={1}
                params={{ kind: "statute", statute: "4857", page: 1 }}
            />,
        );
        await userEvent.click(infoTip(messages.review.queue.summary.totalsTitle));
        expect(openTipText()).toHaveTextContent(messages.review.statutes.help.totals);
    });
});
