import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { ActionsHelp, StatusHelp } from "./statute-detail-help";

const { detail, help } = messages.review.statutes;

describe("statute detail help", () => {
    it("explains approve and reject in a tip on the line above the buttons", async () => {
        renderWithIntl(<ActionsHelp />);
        expect(screen.getByText(detail.actionsTopic)).toBeInTheDocument();
        await userEvent.click(infoTip(detail.actionsTopic));
        expect(openTipText()).toHaveTextContent(help.actions);
    });

    it("explains the status in a tip", async () => {
        renderWithIntl(<StatusHelp />);
        await userEvent.click(infoTip(detail.statusTopic));
        expect(openTipText()).toHaveTextContent(help.statusStrip);
    });
});
