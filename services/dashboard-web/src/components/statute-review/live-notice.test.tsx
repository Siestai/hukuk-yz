import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { LiveNotice } from "./live-notice";

describe("LiveNotice", () => {
    it("links to the published record and explains the notice in a tip beside the link", async () => {
        renderWithIntl(
            <LiveNotice
                id="6c2e8b3f-4d55-4e90-8b72-1f308c9dae21"
                queue={{ kind: "statute", statute: "4857", page: 1 }}
            />,
        );
        const { detail, help } = messages.review.statutes;
        expect(screen.getByRole("link", { name: detail.liveLink })).toBeInTheDocument();
        await userEvent.click(infoTip(detail.liveTopic));
        expect(openTipText()).toHaveTextContent(help.liveNotice);
    });
});
