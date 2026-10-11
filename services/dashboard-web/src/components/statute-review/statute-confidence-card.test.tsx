import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, openTipText, renderWithIntl } from "@/test/intl";
import { StatuteConfidenceCard } from "./statute-confidence-card";

const { confidence, help } = messages.review.statutes;
const { statuteWarning } = messages.enums;

describe("StatuteConfidenceCard help", () => {
    it("explains the card, the reasons and the other warnings", async () => {
        renderWithIntl(
            <StatuteConfidenceCard
                band="medium"
                reasons={["exception_effective"]}
                warnings={["exception_effective", "footnote_marker_not_found"]}
            />,
        );
        await userEvent.click(infoTip(confidence.title));
        expect(openTipText()).toHaveTextContent(help.confidence);
        await userEvent.click(infoTip(confidence.reasons));
        expect(openTipText()).toHaveTextContent(help.confidenceReasons);
        await userEvent.click(infoTip(confidence.warnings));
        expect(openTipText()).toHaveTextContent(help.confidenceWarnings);
    });

    it("gives each reason its own text, also when the code carries a detail", async () => {
        renderWithIntl(
            <StatuteConfidenceCard
                band="low"
                reasons={["number_skipped:main:86->88"]}
                warnings={["number_skipped:main:86->88"]}
            />,
        );
        await userEvent.click(infoTip(`${statuteWarning.number_skipped}:main:86->88`));
        expect(openTipText()).toHaveTextContent(help.reason.number_skipped);
    });

    it("renders a code without a text with no tip and no error", () => {
        renderWithIntl(
            <StatuteConfidenceCard band="low" reasons={["not_a_real_code"]} warnings={[]} />,
        );
        expect(screen.queryByRole("button", { name: /not_a_real_code/ })).toBeNull();
    });
});
