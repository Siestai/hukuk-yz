import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { infoTip, renderWithIntl } from "@/test/intl";
import { TotalsCard } from "./totals-card";

describe("TotalsCard", () => {
    it("shows the approved and rejected counts with a tip on the title", () => {
        renderWithIntl(<TotalsCard approved={1200} rejected={3} />);
        expect(screen.getByText("1.200")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
        expect(infoTip(messages.review.queue.summary.totalsTitle)).toBeInTheDocument();
    });
});
