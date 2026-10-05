import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { HelpTip } from "./help-tip";

describe("HelpTip", () => {
    it("names the button after the topic and reads the help text when activated", async () => {
        renderWithIntl(<HelpTip name="colDate" topic="Tarih" />);
        await userEvent.click(infoTip("Tarih"));
        expect(openTipText()).toHaveTextContent(messages.review.queue.help.colDate);
    });

    it("puts the brand name into the texts that mention it", async () => {
        renderWithIntl(<HelpTip name="title" topic="İnceleme kuyruğu" />);
        await userEvent.click(infoTip("İnceleme kuyruğu"));
        expect(openTipText()).toHaveTextContent(`${messages.brand.name}, iş ve sosyal güvenlik`);
        expect(openTipText()).not.toHaveTextContent("{brand}");
    });

    it("renders nothing for a reason code without a text", () => {
        renderWithIntl(<HelpTip name="reason.not_a_real_code" topic="x" />);
        expect(screen.queryByRole("button")).toBeNull();
    });
});
