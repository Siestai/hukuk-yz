import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { StatuteHeader } from "./statute-header";

describe("StatuteHeader", () => {
    it("explains the screen in a tip beside the heading", async () => {
        renderWithIntl(
            <StatuteHeader
                statuteNumber="4857"
                statuteTitle="4857 sayılı İş Kanunu"
                articleNo="18"
                heading="Feshin geçerli sebebe dayandırılması"
                band="medium"
                status="pending"
                latestSnapshotDate="2026-04-22"
                queue={{ kind: "statute", statute: "4857", page: 1 }}
            />,
        );
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("4857 · m. 18");
        await userEvent.click(infoTip(messages.review.statutes.detail.topic));
        expect(openTipText()).toHaveTextContent(messages.review.statutes.help.detailTitle);
    });
});
